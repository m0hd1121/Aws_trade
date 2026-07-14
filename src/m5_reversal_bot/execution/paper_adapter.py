"""PAPER mode — simulated fills against REAL live/demo market prices. Uses
the same MarketDataFeed the live/demo adapter would (typically MT5's data
feed, read-only), so paper trading experiences genuine spread/price action
without ever sending a real order to the broker.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from ..core.enums import Direction, Instrument
from ..data.feed import MarketDataFeed
from .broker_interface import AccountInfo, ExecutionAdapter, OrderResult, PositionInfo
from .simulation import SimulationBroker


class PaperExecutionAdapter(ExecutionAdapter):
    def __init__(self, feed: MarketDataFeed, initial_equity: float, spread_model: Dict[str, float], slippage_model: Dict[str, float]):
        self.feed = feed
        self.broker = SimulationBroker(initial_equity, spread_model, slippage_model)

    def connect(self) -> None:
        self.feed.connect()

    def disconnect(self) -> None:
        self.feed.disconnect()

    def is_connected(self) -> bool:
        return self.feed.is_connected()

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
        bid, ask, time = self.feed.get_current_tick(instrument)
        return self.broker.place_market(instrument, direction, stop_price, tp1_price, volume, bid, ask, time)

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
        bid, ask, time = self.feed.get_current_tick(p.instrument)
        return self.broker.close_fraction(position_id, fraction, bid, ask, time)

    def close_position(self, position_id: str) -> OrderResult:
        return self.close_position_fraction(position_id, 1.0)

    def get_current_spread(self, instrument: Instrument) -> float:
        return self.feed.get_spread(instrument)

    def pump(self, instrument: Instrument, time: datetime) -> List[dict]:
        bid, ask, tick_time = self.feed.get_current_tick(instrument)
        return self.broker.process_price(instrument, bid, ask, tick_time)
