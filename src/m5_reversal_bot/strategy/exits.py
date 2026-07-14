"""Section 6 — Exits (TP1, break-even, runner trail)."""

from __future__ import annotations

from typing import List, Optional, Tuple

from ..core.constants import EXITS, InstrumentConstants
from ..core.enums import Direction
from ..core.models import LiquidityPool
from .liquidity import find_target_pools, nearest_target_pool


def compute_tp1(
    entry_price: float,
    stop_distance: float,
    direction: Direction,
    pools: List[LiquidityPool],
    inst_constants: InstrumentConstants,
) -> Tuple[float, float, Optional[LiquidityPool]]:
    """6.1 — TP1 = +2.0R exactly, OR the nearest qualified opposing pool if
    it sits between +2.0R and +2.5R, in which case TP1 is fronted by the
    instrument's pool offset. Returns (tp1_price, r_multiple, pool_used)."""
    fixed_tp1 = (
        entry_price + EXITS.tp1_r_multiple * stop_distance
        if direction == Direction.LONG
        else entry_price - EXITS.tp1_r_multiple * stop_distance
    )
    target = nearest_target_pool(pools, entry_price, direction)
    if target is not None and stop_distance > 0:
        distance = abs(target.price - entry_price)
        r = distance / stop_distance
        if EXITS.tp1_r_multiple <= r <= EXITS.tp1_pool_window_max_r:
            offset = inst_constants.pool_frontrun_offset
            tp1 = target.price - offset if direction == Direction.LONG else target.price + offset
            actual_r = abs(tp1 - entry_price) / stop_distance
            return tp1, actual_r, target
    return fixed_tp1, EXITS.tp1_r_multiple, None


def compute_runner_target(
    entry_price: float,
    tp1_price: float,
    direction: Direction,
    pools: List[LiquidityPool],
    inst_constants: InstrumentConstants,
    tp1_pool: Optional[LiquidityPool] = None,
) -> Optional[float]:
    """6.3 — the runner's final target is the NEXT qualified pool beyond
    TP1. `tp1_pool` (if TP1 was itself pool-based) is excluded from
    consideration — a price-only ">" filter against `tp1_price` isn't
    enough, since TP1 is fronted 2 pips/$0.60 short of its pool and that
    same pool would otherwise still satisfy "price > tp1_price" and get
    picked as its own "next" target.
    """
    candidates = [p for p in find_target_pools(pools, direction) if p is not tp1_pool]
    if direction == Direction.LONG:
        beyond = [p for p in candidates if p.price > tp1_price]
        if not beyond:
            return None
        nearest = min(beyond, key=lambda p: p.price)
        return nearest.price - inst_constants.pool_frontrun_offset
    beyond = [p for p in candidates if p.price < tp1_price]
    if not beyond:
        return None
    nearest = max(beyond, key=lambda p: p.price)
    return nearest.price + inst_constants.pool_frontrun_offset


def breakeven_stop(direction: Direction, entry_price: float, spread: float, commission_equivalent: float = 0.0) -> float:
    """6.2 — stop moves to entry + costs, only after TP1 has filled."""
    costs = spread + commission_equivalent
    return entry_price + costs if direction == Direction.LONG else entry_price - costs


def trail_stop_from_swing(direction: Direction, protective_swing_price: float, buffer: float) -> float:
    """6.3 — after each new M5 BOS in the trade's direction, move the stop
    to just beyond the most recent confirmed M5 swing (+/- the 5.2 buffer)."""
    return (
        protective_swing_price - buffer
        if direction == Direction.LONG
        else protective_swing_price + buffer
    )


def r_multiple(direction: Direction, entry_price: float, exit_price: float, stop_distance: float) -> float:
    if stop_distance == 0:
        return 0.0
    signed = (exit_price - entry_price) if direction == Direction.LONG else (entry_price - exit_price)
    return signed / stop_distance
