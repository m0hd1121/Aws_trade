"""The mode-agnostic runner: wires a market data feed, an execution
adapter, one `InstrumentEngine` per traded instrument, and an
`OrderManager` together into a single polling loop. BACKTEST does not use
this runner at all (see backtest/engine.py, which replays history through
the same `InstrumentEngine` without a live loop); PAPER, DEMO, and LIVE
all use this runner, differing only in which feed/adapter get built.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional

from ..core.clock import now_gmt
from ..core.config import REPO_ROOT, RuntimeConfig, app_settings
from ..core.constants import get_instrument_constants, verify_strategy_integrity
from ..core.enums import Instrument, Mode, StrategyStage
from ..data.candle_aggregator import CandleAggregator
from ..data.feed import MarketDataFeed
from ..data.mt5_feed import MT5MarketDataFeed
from ..data.news_feed import load_holiday_calendar, load_static_news_events
from ..execution.backtest_adapter import BacktestExecutionAdapter
from ..execution.broker_interface import ExecutionAdapter
from ..execution.mt5_adapter import MT5ExecutionAdapter
from ..execution.order_manager import OrderManager
from ..execution.paper_adapter import PaperExecutionAdapter
from ..persistence import db, repository
from ..risk_manager.account_state import AccountStateManager
from ..strategy.engine import EngineDependencies, InstrumentEngine

log = logging.getLogger("m5_reversal_bot.runner")

REFERENCE_SYMBOL = {Instrument.EURUSD: "GBPUSD", Instrument.XAUUSD: "XAGUSD"}


class BotRunner:
    def __init__(self, mode: Mode, config: RuntimeConfig):
        verify_strategy_integrity()  # refuse to run against an unverified rulebook

        self.mode = mode
        self.config = config
        self.instruments: List[Instrument] = [Instrument(i) for i in config.enabled_instruments]

        self._stop_flag = True
        self._paused = False
        self._emergency = False
        self._task: Optional[asyncio.Task] = None

        self.account_state = AccountStateManager(mode, config.initial_equity, clock=now_gmt)
        self.holiday_calendar = load_holiday_calendar(Path(app_settings.holiday_calendar_path))
        self.news_events = load_static_news_events(Path(REPO_ROOT / "config" / "news_events_example.yaml"))

        self.feed: Optional[MarketDataFeed] = None
        self.adapter: Optional[ExecutionAdapter] = None
        self.aggregators: Dict[Instrument, CandleAggregator] = {}
        self.reference_aggregators: Dict[Instrument, CandleAggregator] = {}
        self.engines: Dict[Instrument, InstrumentEngine] = {}
        self.order_managers: Dict[Instrument, OrderManager] = {}

        self._build_components()

    # ------------------------------------------------------------------
    def _build_components(self) -> None:
        symbol_map = self.config.raw.get("mt5", {}).get("symbol_map", {})

        if self.mode in (Mode.DEMO, Mode.LIVE):
            self.feed = MT5MarketDataFeed(app_settings.mt5, symbol_map)
            self.adapter = MT5ExecutionAdapter(app_settings.mt5, symbol_map)
        elif self.mode == Mode.PAPER:
            self.feed = MT5MarketDataFeed(app_settings.mt5, symbol_map)  # read-only price source
            backtest_cfg = self.config.backtest
            self.adapter = PaperExecutionAdapter(
                self.feed, self.config.initial_equity,
                backtest_cfg.get("spread_model", {}), backtest_cfg.get("slippage_model", {}),
            )
        else:
            raise ValueError(f"BotRunner does not handle mode={self.mode} — use backtest/engine.py instead")

        db.init_db()
        with db.session_scope() as s:
            account = repository.get_or_create_account(s, self.mode, self.config.initial_equity)
            self._account_id = account.id

        for instrument in self.instruments:
            self.aggregators[instrument] = CandleAggregator(self.feed, instrument)
            self.reference_aggregators[instrument] = None  # built lazily via _reference_candles

            deps = EngineDependencies(
                news_events_provider=lambda _t, i=instrument: self._news_for(i),
                holiday_calendar=self.holiday_calendar,
                account_snapshot_provider=self.account_state.snapshot,
                reference_candles_provider=lambda i=instrument: self._reference_candles(i),
                current_spread_provider=lambda i=instrument: self.aggregators[i].current_spread(),
                bracket_order_supported=lambda: True,
            )
            self.engines[instrument] = InstrumentEngine(instrument, self.mode, deps)
            self.order_managers[instrument] = OrderManager(self.adapter, self.mode, self._account_id)

    def _news_for(self, instrument: Instrument):
        return self.news_events

    def _reference_candles(self, instrument: Instrument):
        symbol = REFERENCE_SYMBOL[instrument]
        agg = self.reference_aggregators.get(instrument)
        if agg is None:
            return []
        return agg.m5

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if not self._stop_flag:
            return
        self._stop_flag = False
        self._emergency = False
        self.adapter.connect()
        self.feed.connect()
        for instrument, agg in self.aggregators.items():
            agg.bootstrap()
        self._task = asyncio.ensure_future(self._run_forever())
        log.info("bot started mode=%s instruments=%s", self.mode.value, [i.value for i in self.instruments])

    def stop(self) -> None:
        self._stop_flag = True
        log.info("bot stop requested")

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def restart(self) -> None:
        self.stop()
        self._build_components()
        self.start()

    def reset_session(self) -> None:
        for engine in self.engines.values():
            engine.reset_session()
        log.info("session state reset (persisted trade history untouched)")

    def emergency_stop(self) -> None:
        self._emergency = True
        with db.session_scope() as s:
            for instrument, engine in self.engines.items():
                actions = engine.emergency_stop()
                self.order_managers[instrument].handle_actions(actions, s)
        self._stop_flag = True
        log.warning("EMERGENCY STOP triggered — all positions/orders flattened")

    # ------------------------------------------------------------------ main loop
    async def _run_forever(self) -> None:
        while not self._stop_flag:
            if self._paused:
                await asyncio.sleep(self.config.poll_interval_seconds)
                continue
            try:
                self._tick()
            except Exception:
                log.exception("tick failed")
                with db.session_scope() as s:
                    repository.log_system(s, "ERROR", "runner", "tick failed", {"mode": self.mode.value})
            await asyncio.sleep(self.config.poll_interval_seconds)

    def _tick(self) -> None:
        now = now_gmt()
        with db.session_scope() as s:
            repository.log_connection_health(s, "data_feed", "UP" if self.feed.is_connected() else "DOWN")
            repository.log_connection_health(s, "execution_adapter", "UP" if self.adapter.is_connected() else "DOWN")

            for instrument in self.instruments:
                agg = self.aggregators[instrument]
                engine = self.engines[instrument]
                om = self.order_managers[instrument]

                for c in agg.poll_new_h4():
                    pass  # reserved: H4 context, not yet consumed by the engine directly
                for c in agg.poll_new_h1():
                    engine.process_h1_candle(c)
                for c in agg.poll_new_m5():
                    actions = engine.process_m5_candle(c)
                    om.handle_actions(actions, s)

                om.poll_fills(engine, s, now)

                news_actions = engine.check_unscheduled_news_flatten(now)
                om.handle_actions(news_actions, s)

    # ------------------------------------------------------------------ dashboard
    def snapshot_for_dashboard(self) -> dict:
        snap = self.account_state.snapshot()
        return {
            "mode": self.mode.value,
            "paused": self._paused,
            "stopped": self._stop_flag,
            "emergency": self._emergency,
            "account": {
                "equity_current": snap.equity_current,
                "equity_start_of_day": snap.equity_start_of_day,
                "daily_realized_loss_percent": snap.daily_realized_loss_percent,
                "weekly_realized_loss_percent": snap.weekly_realized_loss_percent,
                "consecutive_losses_running": snap.consecutive_losses_running,
                "trades_today": snap.trades_today,
                "monthly_brake_active": snap.monthly_brake_active,
                "in_recovery_mode": snap.in_recovery_mode,
            },
            "instruments": {
                i.value: {
                    "stage": e.stage.value,
                    "active_trade": e.active_trade.status.value if e.active_trade else None,
                    "pending_trade": e.pending_trade.status.value if e.pending_trade else None,
                    "day_trading_allowed": e.day_trading_allowed,
                    "day_block_reason": e.day_block_reason,
                }
                for i, e in self.engines.items()
            },
        }
