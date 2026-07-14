from __future__ import annotations

from m5_reversal_bot.core.enums import Direction
from m5_reversal_bot.strategy import structure


def test_swing_high_detected_and_confirmed_after_two_candles(builder):
    # candle index 5 has the highest high; 2 before / 2 after are lower.
    for i in range(10):
        high = 1.0100 if i == 5 else 1.0000
        builder.add(1.0000, high, 0.9995, 1.0000)
    candles = builder.build()

    swings = structure.find_swing_points(candles, "HIGH")
    assert len(swings) == 1
    swing = swings[0]
    assert swing.candle_index == 5
    assert swing.price == 1.0100
    # confirmed only after the 2nd subsequent candle (index 7) closes
    assert swing.confirmed_time == candles[7].close_time


def test_swing_low_mirrors_swing_high(builder):
    for i in range(10):
        low = 0.9900 if i == 5 else 1.0000
        builder.add(1.0000, 1.0005, low, 1.0000)
    candles = builder.build()

    swings = structure.find_swing_points(candles, "LOW")
    assert len(swings) == 1
    assert swings[0].candle_index == 5
    assert swings[0].price == 0.9900


def test_bos_requires_body_close_not_wick(builder):
    # A candle whose wick exceeds the swing but body closes below it must NOT count as a BOS.
    for i in range(10):
        high = 1.0100 if i == 5 else 1.0000
        builder.add(1.0000, high, 0.9995, 1.0000)
    candles = builder.build()
    swing = structure.find_swing_points(candles, "HIGH")[0]

    from tests.conftest import make_candle
    from m5_reversal_bot.core.enums import Instrument

    wick_candle = make_candle(Instrument.EURUSD, "M5", candles[-1].close_time, 1.0050, 1.0150, 1.0040, 1.0050)
    assert structure.detect_bos(wick_candle, swing, Direction.LONG) is False

    body_close_candle = make_candle(Instrument.EURUSD, "M5", candles[-1].close_time, 1.0050, 1.0150, 1.0040, 1.0120)
    assert structure.detect_bos(body_close_candle, swing, Direction.LONG) is True


def test_choch_finds_first_body_close_beyond_last_confirmed_opposite_swing(builder):
    # Build a swing HIGH at index 5 (confirmed after index 7), then a candle
    # at index 9 that body-closes above it -> bullish CHoCH.
    for i in range(10):
        high = 1.0100 if i == 5 else 1.0000
        close = 1.0150 if i == 9 else 1.0000
        builder.add(1.0000, max(high, close + 0.0005), 0.9995, close)
    candles = builder.build()

    swing_highs, _ = structure.find_all_swings(candles)
    choch = structure.detect_choch(candles, start_index=6, direction=Direction.LONG, swings_of_opposite_kind=swing_highs)
    assert choch is not None
    assert choch.confirm_candle_index == 9
    assert choch.broken_swing.candle_index == 5
