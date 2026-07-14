"""Definition 1.14 — Chop Condition."""

from __future__ import annotations

from typing import List

from ..core.constants import CHOP
from ..core.enums import Direction
from ..core.models import Candle, CHoCH


def is_chop(
    candles: List[Candle],
    up_to_index: int,
    recent_chochs: List[CHoCH],
    planned_stop_distance: float,
) -> bool:
    """1.14 — chop if, within the last 24 M5 candles, there have been >=2
    bullish AND >=2 bearish CHoCHs, OR the total range of the last 12 M5
    candles is smaller than 1.5x the planned stop distance."""
    lb24_start = max(0, up_to_index - CHOP.lookback_candles_for_choch_count + 1)
    recent = [
        ch for ch in recent_chochs
        if lb24_start <= ch.confirm_candle_index <= up_to_index
    ]
    bullish_count = sum(1 for ch in recent if ch.direction == Direction.LONG)
    bearish_count = sum(1 for ch in recent if ch.direction == Direction.SHORT)
    cond1 = bullish_count >= CHOP.min_bullish_chochs and bearish_count >= CHOP.min_bearish_chochs

    lb12_start = max(0, up_to_index - CHOP.lookback_candles_for_range + 1)
    window = candles[lb12_start:up_to_index + 1]
    cond2 = False
    if window and planned_stop_distance > 0:
        total_range = max(c.high for c in window) - min(c.low for c in window)
        cond2 = total_range < CHOP.range_to_stop_multiple * planned_stop_distance

    return cond1 or cond2
