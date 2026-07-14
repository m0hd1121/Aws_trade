"""Event-driven backtester. Replays historical M5/H1 bars through the
IDENTICAL `InstrumentEngine` + `OrderManager` pair the live/demo/paper
runner uses, against a `BacktestExecutionAdapter` (same `SimulationBroker`
mechanics as paper trading). This is what makes "the same strategy logic
is used across backtesting, paper trading, demo trading, and live trading"
literally true rather than a claim: there is exactly one decision-making
code path, and this module never reimplements it.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

from ..core.clock import to_gmt
from ..core.config import REPO_ROOT, app_settings
from ..core.constants import verify_strategy_integrity
from ..core.enums import Instrument, Mode
from ..core.models import Candle
from ..data.historical_loader import load_instrument_history
from ..data.news_feed import load_holiday_calendar, load_static_news_events
from ..execution.backtest_adapter import BacktestExecutionAdapter
from ..execution.order_manager import OrderManager
from ..persistence import db, repository
from ..risk_manager.account_state import AccountStateManager
from ..strategy.engine import EngineDependencies, InstrumentEngine
from .report import BacktestReport, build_report

REFERENCE_SYMBOL = {Instrument.EURUSD: "GBPUSD", Instrument.XAUUSD: "XAGUSD"}


class BacktestRunner:
    def __init__(
        self,
        instruments: List[Instrument],
        data_dir: Path,
        start_date: date,
        end_date: date,
        initial_equity: float,
        spread_model: Dict[str, float],
        slippage_model: Dict[str, float],
    ):
        verify_strategy_integrity()

        self.instruments = instruments
        self.start_date = start_date
        self.end_date = end_date
        self.mode = Mode.BACKTEST

        self.adapter = BacktestExecutionAdapter(initial_equity, spread_model, slippage_model)
        self._current_time: datetime = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        self.account_state = AccountStateManager(self.mode, initial_equity, clock=lambda: self._current_time)

        self.news_events = load_static_news_events(Path(REPO_ROOT / "config" / "news_events_example.yaml"))
        self.holiday_calendar = load_holiday_calendar(Path(app_settings.holiday_calendar_path))

        self.histories: Dict[Instrument, dict] = {}
        self.reference_histories: Dict[Instrument, List[Candle]] = {}
        self.engines: Dict[Instrument, InstrumentEngine] = {}
        self.order_managers: Dict[Instrument, OrderManager] = {}

        for instrument in instruments:
            self.histories[instrument] = load_instrument_history(data_dir, instrument)
            ref_symbol = REFERENCE_SYMBOL[instrument]
            ref_path = data_dir / f"{ref_symbol}_M5.csv"
            self.reference_histories[instrument] = []
            if ref_path.exists():
                from ..data.historical_loader import load_csv_candles

                self.reference_histories[instrument] = load_csv_candles(ref_path, instrument, "M5")

            deps = EngineDependencies(
                news_events_provider=lambda _t: self.news_events,
                holiday_calendar=self.holiday_calendar,
                account_snapshot_provider=self.account_state.snapshot,
                reference_candles_provider=lambda i=instrument: self._reference_window(i),
                current_spread_provider=lambda i=instrument: self.adapter.broker.spread_for(i),
                bracket_order_supported=lambda: True,
            )
            self.engines[instrument] = InstrumentEngine(instrument, self.mode, deps)
            self.order_managers[instrument] = OrderManager(
                self.adapter, self.mode, account_id=None,
                on_trade_closed=lambda t: self.account_state.record_trade_result(t.instrument, t.session, t.r_result, t.pnl or 0.0),
            )

        self._reference_index: Dict[Instrument, int] = {i: 0 for i in instruments}

    def _reference_window(self, instrument: Instrument) -> List[Candle]:
        idx = self._reference_index[instrument]
        return self.reference_histories[instrument][:idx]

    def _merged_m5_timeline(self):
        merged = []
        for instrument in self.instruments:
            for c in self.histories[instrument]["M5"]:
                d = to_gmt(c.open_time).date()
                if self.start_date <= d <= self.end_date:
                    merged.append(c)
        merged.sort(key=lambda c: c.open_time)
        return merged

    def run(self) -> BacktestReport:
        db.init_db()
        with db.session_scope() as s:
            account = repository.get_or_create_account(s, self.mode, self.account_state.equity_current)
            for om in self.order_managers.values():
                om.account_id = account.id

        h1_pointers = {i: 0 for i in self.instruments}
        timeline = self._merged_m5_timeline()

        with db.session_scope() as s:
            for candle in timeline:
                self._current_time = candle.close_time
                instrument = candle.instrument
                engine = self.engines[instrument]
                om = self.order_managers[instrument]

                h1_series = self.histories[instrument]["H1"]
                while h1_pointers[instrument] < len(h1_series) and h1_series[h1_pointers[instrument]].close_time <= candle.close_time:
                    engine.process_h1_candle(h1_series[h1_pointers[instrument]])
                    h1_pointers[instrument] += 1

                ref_series = self.reference_histories.get(instrument, [])
                while (
                    self._reference_index[instrument] < len(ref_series)
                    and ref_series[self._reference_index[instrument]].close_time <= candle.close_time
                ):
                    self._reference_index[instrument] += 1

                # Resolve fills/stops/TPs from ORDERS ALREADY RESTING
                # against this bar's range before the engine reacts to this
                # bar's own close. Otherwise an order the engine submits
                # off THIS candle's close would be checked against this
                # same candle's low/high — a low that, chronologically,
                # already happened before the close that created the order.
                fill_events = self.adapter.advance_bar(candle)
                for ev in fill_events:
                    om._translate_event(ev, engine, s)

                actions = engine.process_m5_candle(candle)
                om.handle_actions(actions, s)

                news_actions = engine.check_unscheduled_news_flatten(candle.close_time)
                om.handle_actions(news_actions, s)

            report = build_report(s, self.mode)
        return report
