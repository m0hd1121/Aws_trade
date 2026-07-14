"""Definition 1.7 (displacement) and 1.8 (Fair Value Gap)."""

from __future__ import annotations

from typing import List, Optional, Tuple

from ..core.constants import STRUCTURE
from ..core.enums import Direction
from ..core.models import Candle, FVG


def is_displacement_candle(candles: List[Candle], k: int) -> bool:
    """1.7 — body larger than EACH of the 6 preceding M5 candles' bodies."""
    lookback = STRUCTURE.displacement_body_lookback
    if k - lookback < 0:
        return False
    body = candles[k].body_size
    return all(body > candles[k - j].body_size for j in range(1, lookback + 1))


def detect_fvg_triple(candles: List[Candle], i1: int, i3: int, direction: Direction) -> Optional[FVG]:
    """1.8 — 3-candle sequence: candle1.high < candle3.low (bullish) or
    candle1.low > candle3.high (bearish)."""
    c1, c3 = candles[i1], candles[i3]
    if direction == Direction.LONG:
        if c1.high < c3.low:
            return FVG(
                instrument=c1.instrument,
                direction=Direction.LONG,
                candle1_time=c1.open_time,
                candle3_time=c3.open_time,
                gap_low=c1.high,
                gap_high=c3.low,
            )
    else:
        if c1.low > c3.high:
            return FVG(
                instrument=c1.instrument,
                direction=Direction.SHORT,
                candle1_time=c1.open_time,
                candle3_time=c3.open_time,
                gap_low=c3.high,
                gap_high=c1.low,
            )
    return None


def detect_displacement(
    candles: List[Candle], leg_start_index: int, leg_end_index: int, direction: Direction
) -> Optional[Tuple[int, FVG]]:
    """1.7 + F4 — the CHoCH leg's displacement candle and the FVG it leaves.
    Scans the leg for a candle meeting the body-dominance test whose
    immediate 3-candle triple (k-1, k, k+1) also satisfies 1.8. Returns the
    earliest qualifying (displacement_index, fvg) pair, or None.
    """
    n = len(candles)
    hi = min(leg_end_index, n - 2)
    for k in range(max(leg_start_index, 1), hi + 1):
        if k - 1 < 0 or k + 1 >= n:
            continue
        if not is_displacement_candle(candles, k):
            continue
        fvg = detect_fvg_triple(candles, k - 1, k + 1, direction)
        if fvg is not None:
            return k, fvg
    return None
