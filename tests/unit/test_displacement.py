from __future__ import annotations

from m5_reversal_bot.core.enums import Direction
from m5_reversal_bot.strategy import displacement


def test_displacement_requires_body_larger_than_each_of_six_preceding(builder):
    for _ in range(6):
        builder.add(1.1000, 1.1002, 1.0998, 1.1001)  # small bodies ~0.0001
    builder.add(1.1001, 1.1030, 1.1000, 1.1028)        # big body ~0.0027
    candles = builder.build()
    assert displacement.is_displacement_candle(candles, 6) is True
    assert displacement.is_displacement_candle(candles, 5) is False  # not enough lookback history distinction


def test_displacement_and_fvg_found_together(builder):
    for _ in range(6):
        builder.add(1.1000, 1.1002, 1.0998, 1.1001)
    builder.add(1.0999, 1.1001, 1.0997, 1.1000)   # candle1 of the triple: high=1.1001
    builder.add(1.1000, 1.1030, 1.0999, 1.1028)   # displacement candle (index 7)
    builder.add(1.1028, 1.1032, 1.1010, 1.1029)   # candle3: low=1.1010 > candle1.high(1.1001) -> FVG
    candles = builder.build()

    result = displacement.detect_displacement(candles, leg_start_index=6, leg_end_index=7, direction=Direction.LONG)
    assert result is not None
    idx, fvg = result
    assert idx == 7
    assert fvg.gap_low == 1.1001
    assert fvg.gap_high == 1.1010
    assert round(fvg.ce, 5) == round((1.1001 + 1.1010) / 2, 5)


def test_no_displacement_returns_none_when_body_not_dominant(builder):
    for _ in range(8):
        builder.add(1.1000, 1.1010, 1.0990, 1.1005)  # uniform, largish bodies — none dominates
    candles = builder.build()
    result = displacement.detect_displacement(candles, leg_start_index=1, leg_end_index=6, direction=Direction.LONG)
    assert result is None
