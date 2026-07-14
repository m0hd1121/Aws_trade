"""Deterministic fill simulation against historical bars, driven by
`backtest/engine.py` calling `advance_bar()` once per closed M5 candle.
Same `SimulationBroker` mechanics as paper trading — only the price source
differs (historical bars here, live ticks there).
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from ..core.enums import Instrument
from ..core.models import Candle
from .broker_interface import AccountInfo, ExecutionAdapter, OrderResult, PositionInfo
from .simulation import SimulationBroker


class BacktestExecutionAdapter(ExecutionAdapter):
    def __init__(self, initial_equity: float, spread_model: Dict[str, float], slippage_model: Dict[str, float]):
        self.broker = SimulationBroker(initial_equity, spread_model, slippage_model)
        self._connected = False
        self._last_bar: Dict[Instrument, Candle] = {}

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_account_info(self) -> AccountInfo:
        return AccountInfo(equity=self.broker.equity, balance=self.broker.balance, currency="USD", margin_free=self.broker.equity)

    def get_open_positions(self) -> List[PositionInfo]:
        return [
            PositionInfo(
                position_id=p.position_id, instrument=p.instrument, direction=p.direction, volume=p.volume,
                open_price=p.open_price, stop_price=p.stop_price, tp_price=p.tp_price, unrealized_pnl=p.unrealized_pnl,
            )
            for p in self.broker.positions.values()
        ]

    def place_bracket_limit_order(self, instrument, direction, entry_price, stop_price, tp1_price, volume, valid_until) -> OrderResult:
        return self.broker.place_limit(instrument, direction, entry_price, stop_price, tp1_price, volume, valid_until)

    def place_bracket_market_order(self, instrument, direction, stop_price, tp1_price, volume) -> OrderResult:
        bar = self._last_bar.get(instrument)
        if bar is None:
            return OrderResult(success=False, order_id=None, filled=False, fill_price=None, fill_time=None, error="no bar data yet")
        spread = self.broker.spread_for(instrument)
        bid, ask = bar.close - spread / 2, bar.close + spread / 2
        return self.broker.place_market(instrument, direction, stop_price, tp1_price, volume, bid, ask, bar.open_time)

    def cancel_order(self, order_id: str) -> bool:
        return self.broker.cancel(order_id)

    def poll_order_status(self, order_id: str) -> OrderResult:
        return self.broker.order_status(order_id)

    def modify_stop(self, position_id: str, new_stop_price: float) -> bool:
        return self.broker.modify_stop(position_id, new_stop_price)

    def modify_target(self, position_id: str, new_tp_price) -> bool:
        return self.broker.modify_target(position_id, new_tp_price)

    def close_position_fraction(self, position_id: str, fraction: float) -> OrderResult:
        p = self.broker.positions.get(position_id)
        if p is None:
            return OrderResult(success=False, order_id=position_id, filled=False, fill_price=None, fill_time=None, error="unknown position")
        bar = self._last_bar.get(p.instrument)
        spread = self.broker.spread_for(p.instrument)
        bid, ask = bar.close - spread / 2, bar.close + spread / 2
        return self.broker.close_fraction(position_id, fraction, bid, ask, bar.open_time)

    def close_position(self, position_id: str) -> OrderResult:
        return self.close_position_fraction(position_id, 1.0)

    def get_current_spread(self, instrument: Instrument) -> float:
        return self.broker.spread_for(instrument)

    def pump(self, instrument: Instrument, time: datetime) -> List[dict]:
        # No-op for backtest: fills/stops/TPs are resolved in advance_bar()
        # using the bar's full OHLC range, which is more accurate than a
        # single synthetic tick.
        return []

    def advance_bar(self, candle: Candle) -> List[dict]:
        self._last_bar[candle.instrument] = candle
        spread = self.broker.spread_for(candle.instrument)
        return self.broker.process_bar(candle.instrument, candle.high, candle.low, candle.close, spread, candle.open_time)
