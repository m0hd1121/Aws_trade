"""Rolling candle buffer over a MarketDataFeed. Emits each newly-closed
candle exactly once, in order, for the strategy engine to consume.

The window defaults to ~2 weeks of M5 bars (needed for Definition 1.5's
previous-week high/low pool) — at a few hundred bytes per candle this is a
few MB, negligible; "low RAM/CPU" in this system is about not shipping a
GPU/ML runtime, not about trimming a couple thousand OHLC tuples.
"""

from __future__ import annotations

from typing import List, Optional

from ..core.enums import Instrument
from ..core.models import Candle
from .feed import MarketDataFeed

DEFAULT_M5_WINDOW = 4500   # ~2 weeks of M5 bars, 24h/day
DEFAULT_H1_WINDOW = 500
DEFAULT_H4_WINDOW = 200


class CandleAggregator:
    def __init__(
        self,
        feed: MarketDataFeed,
        instrument: Instrument,
        m5_window: int = DEFAULT_M5_WINDOW,
        h1_window: int = DEFAULT_H1_WINDOW,
        h4_window: int = DEFAULT_H4_WINDOW,
    ):
        self.feed = feed
        self.instrument = instrument
        self.m5_window = m5_window
        self.h1_window = h1_window
        self.h4_window = h4_window

        self.m5: List[Candle] = []
        self.h1: List[Candle] = []
        self.h4: List[Candle] = []
        self._last_m5_time = None
        self._last_h1_time = None
        self._last_h4_time = None

    def bootstrap(self) -> None:
        self.m5 = self.feed.get_recent_candles(self.instrument, "M5", self.m5_window)
        self.h1 = self.feed.get_recent_candles(self.instrument, "H1", self.h1_window)
        self.h4 = self.feed.get_recent_candles(self.instrument, "H4", self.h4_window)
        self._last_m5_time = self.m5[-1].open_time if self.m5 else None
        self._last_h1_time = self.h1[-1].open_time if self.h1 else None
        self._last_h4_time = self.h4[-1].open_time if self.h4 else None

    def _poll(self, timeframe: str, buffer: List[Candle], last_time, window: int, poll_count: int = 10):
        latest = self.feed.get_recent_candles(self.instrument, timeframe, poll_count)
        new = [c for c in latest if last_time is None or c.open_time > last_time]
        new.sort(key=lambda c: c.open_time)
        buffer.extend(new)
        if len(buffer) > window:
            del buffer[: len(buffer) - window]
        new_last = buffer[-1].open_time if buffer else last_time
        return new, new_last

    def poll_new_m5(self) -> List[Candle]:
        new, self._last_m5_time = self._poll("M5", self.m5, self._last_m5_time, self.m5_window)
        return new

    def poll_new_h1(self) -> List[Candle]:
        new, self._last_h1_time = self._poll("H1", self.h1, self._last_h1_time, self.h1_window, poll_count=5)
        return new

    def poll_new_h4(self) -> List[Candle]:
        new, self._last_h4_time = self._poll("H4", self.h4, self._last_h4_time, self.h4_window, poll_count=5)
        return new

    def current_spread(self) -> float:
        return self.feed.get_spread(self.instrument)
