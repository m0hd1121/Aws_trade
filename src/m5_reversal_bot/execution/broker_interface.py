"""Abstract execution adapter. Every adapter (MT5 live/demo, paper,
backtest) implements this same interface so `execution/order_manager.py`
and the strategy engine's action stream drive all four modes identically —
"the same strategy logic is used across backtesting, paper trading, demo
trading, and live trading" holds because this is the only place a trade
instruction ever reaches a broker (real or simulated).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from ..core.enums import Direction, Instrument


@dataclass(frozen=True)
class AccountInfo:
    equity: float
    balance: float
    currency: str
    margin_free: float


@dataclass(frozen=True)
class PositionInfo:
    position_id: str
    instrument: Instrument
    direction: Direction
    volume: float
    open_price: float
    stop_price: Optional[float]
    tp_price: Optional[float]
    unrealized_pnl: float


@dataclass(frozen=True)
class OrderResult:
    success: bool
    order_id: Optional[str]
    filled: bool
    fill_price: Optional[float]
    fill_time: Optional[datetime]
    error: Optional[str] = None


class ExecutionAdapter(ABC):
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def get_account_info(self) -> AccountInfo: ...

    @abstractmethod
    def get_open_positions(self) -> List[PositionInfo]: ...

    @abstractmethod
    def place_bracket_limit_order(
        self,
        instrument: Instrument,
        direction: Direction,
        entry_price: float,
        stop_price: float,
        tp1_price: float,
        volume: float,
        valid_until: datetime,
    ) -> OrderResult:
        """Places entry + SL + TP1 atomically (4.1.3 — no naked entries,
        ever). Returns immediately with the resting order's id; fill is
        reported later via `poll_order_status`/adapter-specific callback."""
        ...

    @abstractmethod
    def place_bracket_market_order(
        self,
        instrument: Instrument,
        direction: Direction,
        stop_price: float,
        tp1_price: float,
        volume: float,
    ) -> OrderResult:
        """4.3 — confirmation market entry. Fills (or fails) immediately."""
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    def poll_order_status(self, order_id: str) -> OrderResult: ...

    @abstractmethod
    def modify_stop(self, position_id: str, new_stop_price: float) -> bool: ...

    @abstractmethod
    def modify_target(self, position_id: str, new_tp_price: Optional[float]) -> bool:
        """Used after TP1 fills to re-point the remaining runner's target
        at the Section 6.3 draw-on-liquidity level (or clear it entirely
        if trailing alone should manage the exit)."""
        ...

    @abstractmethod
    def close_position_fraction(self, position_id: str, fraction: float) -> OrderResult:
        """6.1 — TP1 closes exactly 50% of the position."""
        ...

    @abstractmethod
    def close_position(self, position_id: str) -> OrderResult: ...

    @abstractmethod
    def get_current_spread(self, instrument: Instrument) -> float: ...

    @abstractmethod
    def pump(self, instrument: Instrument, time: datetime) -> List[dict]:
        """Advances internal fill/SL/TP simulation for adapters that need
        one (paper/backtest) and returns standardized events:
        {"type": "FILLED"|"STOP_HIT"|"TP_HIT"|"EXPIRED", "order_id" or
        "position_id", "price", "time"}. The MT5 adapter returns [] — the
        broker handles SL/TP server-side and order_manager detects those
        via `poll_order_status`/`get_open_positions` instead."""
        ...
