from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from m5_reversal_bot.core.enums import Instrument
from m5_reversal_bot.core.models import Candle

GMT = timezone.utc


def make_candle(instrument, timeframe, open_time, o, h, l, c, volume=100.0) -> Candle:
    return Candle(instrument=instrument, timeframe=timeframe, open_time=open_time, open=o, high=h, low=l, close=c, volume=volume)


class CandleSeriesBuilder:
    """Small helper for building deterministic M5 candle series in tests."""

    def __init__(self, instrument=Instrument.EURUSD, start=None, timeframe="M5", step_minutes=5):
        self.instrument = instrument
        self.timeframe = timeframe
        self.step = timedelta(minutes=step_minutes)
        self.t = start or datetime(2025, 1, 6, 0, 0, tzinfo=GMT)  # a Monday
        self.candles: list[Candle] = []

    def add(self, o, h, l, c) -> "CandleSeriesBuilder":
        self.candles.append(make_candle(self.instrument, self.timeframe, self.t, o, h, l, c))
        self.t += self.step
        return self

    def add_flat_run(self, count, price, wiggle=0.00002) -> "CandleSeriesBuilder":
        for _ in range(count):
            self.add(price, price + wiggle, price - wiggle, price)
        return self

    def build(self):
        return self.candles


@pytest.fixture
def builder():
    return CandleSeriesBuilder()
