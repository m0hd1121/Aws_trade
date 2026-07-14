"""Abstract market data feed. All concrete feeds (MT5 live/demo, historical
CSV for backtests) implement this same interface so the bot/runner and
strategy engine never need to know which one is underneath."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Tuple

from ..core.enums import Instrument
from ..core.models import Candle


class MarketDataFeed(ABC):
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def get_recent_candles(self, instrument: Instrument, timeframe: str, count: int) -> List[Candle]:
        """Returns the most recent `count` CLOSED candles, oldest first."""
        ...

    @abstractmethod
    def get_current_tick(self, instrument: Instrument) -> Tuple[float, float, datetime]:
        """Returns (bid, ask, time)."""
        ...

    def get_spread(self, instrument: Instrument) -> float:
        bid, ask, _ = self.get_current_tick(instrument)
        return ask - bid

    @abstractmethod
    def get_reference_candles(self, reference_symbol: str, timeframe: str, count: int) -> List[Candle]:
        """Candles for the SMT correlated reference instrument (GBPUSD /
        XAGUSD), keyed by broker symbol string rather than our Instrument
        enum since the reference isn't one of the two traded instruments."""
        ...
