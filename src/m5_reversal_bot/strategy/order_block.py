"""Definition 1.9 — Order Block."""

from __future__ import annotations

from typing import List, Optional

from ..core.enums import Direction
from ..core.models import Candle, OrderBlock


def find_order_block(candles: List[Candle], displacement_index: int, direction: Direction) -> Optional[OrderBlock]:
    """1.9 — the last opposite-direction candle (full wick-to-wick range)
    immediately before the displacement move. For a long: the last bearish
    candle before the up-displacement. Scans backward from the displacement
    candle for the nearest candle of the opposite color."""
    want_bearish = direction == Direction.LONG
    for i in range(displacement_index - 1, -1, -1):
        c = candles[i]
        if want_bearish and c.is_bearish:
            return OrderBlock(instrument=c.instrument, direction=direction, candle_time=c.open_time, low=c.low, high=c.high)
        if not want_bearish and c.is_bullish:
            return OrderBlock(instrument=c.instrument, direction=direction, candle_time=c.open_time, low=c.low, high=c.high)
    return None


def is_order_block_mitigated(candles: List[Candle], ob: OrderBlock, since_index: int) -> bool:
    """1.9 — "unmitigated" means price has not traded back into the OB's
    full range since the displacement. Checked from the displacement
    candle onward through the current candle."""
    for c in candles[since_index:]:
        if c.low <= ob.high and c.high >= ob.low:
            return True
    return False
