"""Definitions 1.1-1.4 — swing points, BOS, CHoCH.

Pure functions over a chronological candle list (index 0 = oldest). Nothing
here is a "strategy decision" — these are the objective structural building
blocks every downstream rule (sweep, displacement, POI, scoring) reads.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from ..core.constants import STRUCTURE
from ..core.enums import Direction
from ..core.models import Candle, CHoCH, SwingPoint


def find_swing_points(candles: List[Candle], kind: str) -> List[SwingPoint]:
    """1.1 (HIGH) / 1.2 (LOW): a candle whose high/low exceeds the 2 candles
    immediately before AND the 2 immediately after it. Confirmed only after
    the 2nd subsequent candle closes."""
    lb = STRUCTURE.swing_fractal_lookback
    la = STRUCTURE.swing_fractal_lookahead
    swings: List[SwingPoint] = []
    n = len(candles)
    for i in range(lb, n - la):
        c = candles[i]
        if kind == "HIGH":
            is_extreme = all(c.high > candles[i - k].high for k in range(1, lb + 1)) and all(
                c.high > candles[i + k].high for k in range(1, la + 1)
            )
            price = c.high
        else:
            is_extreme = all(c.low < candles[i - k].low for k in range(1, lb + 1)) and all(
                c.low < candles[i + k].low for k in range(1, la + 1)
            )
            price = c.low
        if is_extreme:
            confirm_candle = candles[i + la]
            swings.append(
                SwingPoint(
                    instrument=c.instrument,
                    timeframe=c.timeframe,
                    kind=kind,
                    price=price,
                    candle_time=c.open_time,
                    confirmed_time=confirm_candle.close_time,
                    candle_index=i,
                )
            )
    return swings


def find_all_swings(candles: List[Candle]) -> Tuple[List[SwingPoint], List[SwingPoint]]:
    """Returns (swing_highs, swing_lows), each ordered by candle_index."""
    return find_swing_points(candles, "HIGH"), find_swing_points(candles, "LOW")


def most_recent_confirmed(swings: List[SwingPoint], as_of_time: datetime) -> Optional[SwingPoint]:
    candidates = [s for s in swings if s.confirmed_time <= as_of_time]
    if not candidates:
        return None
    return max(candidates, key=lambda s: s.candle_index)


def detect_bos(candle: Candle, swing: SwingPoint, direction: Direction) -> bool:
    """1.3 — an M5 candle body CLOSE beyond the swing. Wicks never count,
    which is why this checks `candle.close`, never `candle.high`/`.low`."""
    if direction == Direction.LONG:
        return candle.close > swing.price
    return candle.close < swing.price


def detect_choch(
    candles: List[Candle],
    start_index: int,
    direction: Direction,
    swings_of_opposite_kind: List[SwingPoint],
) -> Optional[CHoCH]:
    """1.4 — scan forward from `start_index` (the sweep candle) for the first
    M5 body close beyond the most recent confirmed swing against the
    pre-sweep structure. Bullish CHoCH breaks the last confirmed swing HIGH
    (the "last lower high"); bearish CHoCH breaks the last confirmed swing
    LOW (the "last higher low"). `swings_of_opposite_kind` must be swing
    HIGHs for a LONG CHoCH search, swing LOWs for a SHORT CHoCH search.
    """
    for i in range(start_index, len(candles)):
        c = candles[i]
        ref_swing = most_recent_confirmed(swings_of_opposite_kind, c.close_time)
        if ref_swing is None:
            continue
        if detect_bos(c, ref_swing, direction):
            return CHoCH(
                instrument=c.instrument,
                direction=direction,
                confirm_candle_time=c.open_time,
                confirm_candle_index=i,
                close_price=c.close,
                broken_swing=ref_swing,
            )
    return None


def detect_bos_events_since(
    candles: List[Candle],
    since_index: int,
    direction: Direction,
    swings_in_direction: List[SwingPoint],
) -> List[Tuple[int, SwingPoint]]:
    """6.3 trailing input — every subsequent M5 BOS *in the trade's
    direction* since `since_index`. `swings_in_direction` must be swing
    HIGHs for a LONG trade (continuation breaks upward), swing LOWs for a
    SHORT trade. Each confirmed swing can only trigger one BOS event."""
    events: List[Tuple[int, SwingPoint]] = []
    broken_already: set = set()
    for i in range(since_index, len(candles)):
        c = candles[i]
        ref = most_recent_confirmed(swings_in_direction, c.close_time)
        if ref is None or ref.candle_index in broken_already:
            continue
        if detect_bos(c, ref, direction):
            events.append((i, ref))
            broken_already.add(ref.candle_index)
    return events


def most_recent_confirmed_opposite_swing(
    candles: List[Candle],
    as_of_index: int,
    direction: Direction,
    swings_opposite_kind: List[SwingPoint],
) -> Optional[SwingPoint]:
    """For trailing (6.3): after a BOS in the trade's direction, the new
    stop reference is the most recent confirmed swing on the *protective*
    side — the swing LOW for a LONG trade, swing HIGH for a SHORT trade."""
    as_of_time = candles[as_of_index].close_time
    return most_recent_confirmed(swings_opposite_kind, as_of_time)
