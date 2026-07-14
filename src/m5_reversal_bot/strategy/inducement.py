"""Definition 1.12 — Inducement."""

from __future__ import annotations

from typing import List, Optional

from ..core.enums import Direction
from ..core.models import CHoCH, Inducement, POI, SwingPoint


def find_inducement(
    choch: CHoCH,
    poi: POI,
    direction: Direction,
    swings_low: List[SwingPoint],
    swings_high: List[SwingPoint],
) -> Optional[Inducement]:
    """1.12 — a confirmed M5 swing point formed after the CHoCH, sitting
    between the POI and the CHoCH confirmation extreme (the retracement
    path price must travel to reach the POI). For a LONG setup this is a
    minor swing LOW above the POI (see Section 11.1's worked example); for
    a SHORT setup, a minor swing HIGH below the POI.
    """
    relevant = swings_low if direction == Direction.LONG else swings_high
    candidates = [s for s in relevant if s.candle_index > choch.confirm_candle_index]
    candidates.sort(key=lambda s: s.candle_index)
    for s in candidates:
        if direction == Direction.LONG:
            if poi.zone_high < s.price < choch.close_price:
                return Inducement(instrument=poi.instrument, swing=s)
        else:
            if choch.close_price < s.price < poi.zone_low:
                return Inducement(instrument=poi.instrument, swing=s)
    return None
