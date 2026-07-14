"""Definitions 1.5 (qualified liquidity pools) and 1.6 (sweep vs breakout)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from ..core.clock import (
    asia_window,
    kill_zone_bounds,
    london_session_window,
    previous_day_window,
    previous_week_window,
)
from ..core.constants import STRUCTURE, InstrumentConstants
from ..core.enums import Instrument, PoolType
from ..core.enums import Session as SessionEnum
from ..core.models import Candle, LiquidityPool, Sweep, SwingPoint

LOW_POOL_TYPES = {
    PoolType.ASIA_LOW, PoolType.PDL, PoolType.PWL, PoolType.LONDON_LOW,
    PoolType.LKZ_LOW, PoolType.EQUAL_LOWS,
}
HIGH_POOL_TYPES = {
    PoolType.ASIA_HIGH, PoolType.PDH, PoolType.PWH, PoolType.LONDON_HIGH,
    PoolType.LKZ_HIGH, PoolType.EQUAL_HIGHS,
}


def _extreme_in_window(candles: List[Candle], start: datetime, end: datetime, kind: str) -> Optional[Candle]:
    subset = [c for c in candles if start <= c.open_time < end]
    if not subset:
        return None
    return max(subset, key=lambda c: c.high) if kind == "HIGH" else min(subset, key=lambda c: c.low)


def compute_asia_range(candles: List[Candle], ref_date: datetime) -> Optional[tuple]:
    """1.13 — Asia range (high - low), 00:00-06:00 GMT."""
    start, end = asia_window(ref_date)
    subset = [c for c in candles if start <= c.open_time < end]
    if not subset:
        return None
    hi = max(c.high for c in subset)
    lo = min(c.low for c in subset)
    return hi, lo, hi - lo


def build_session_pools(candles: List[Candle], instrument: Instrument, ref_date: datetime) -> List[LiquidityPool]:
    """Asia H/L, PDH/PDL, PWH/PWL, London session H/L — Definition 1.5."""
    pools: List[LiquidityPool] = []

    a_start, a_end = asia_window(ref_date)
    hi_c = _extreme_in_window(candles, a_start, a_end, "HIGH")
    lo_c = _extreme_in_window(candles, a_start, a_end, "LOW")
    if hi_c:
        pools.append(LiquidityPool(instrument, PoolType.ASIA_HIGH, hi_c.high, a_end, hi_c.open_time))
    if lo_c:
        pools.append(LiquidityPool(instrument, PoolType.ASIA_LOW, lo_c.low, a_end, lo_c.open_time))

    pd_start, pd_end = previous_day_window(ref_date)
    hi_c = _extreme_in_window(candles, pd_start, pd_end, "HIGH")
    lo_c = _extreme_in_window(candles, pd_start, pd_end, "LOW")
    if hi_c:
        pools.append(LiquidityPool(instrument, PoolType.PDH, hi_c.high, pd_end, hi_c.open_time))
    if lo_c:
        pools.append(LiquidityPool(instrument, PoolType.PDL, lo_c.low, pd_end, lo_c.open_time))

    pw_start, pw_end = previous_week_window(ref_date)
    hi_c = _extreme_in_window(candles, pw_start, pw_end, "HIGH")
    lo_c = _extreme_in_window(candles, pw_start, pw_end, "LOW")
    if hi_c:
        pools.append(LiquidityPool(instrument, PoolType.PWH, hi_c.high, pw_end, hi_c.open_time))
    if lo_c:
        pools.append(LiquidityPool(instrument, PoolType.PWL, lo_c.low, pw_end, lo_c.open_time))

    ls_start, ls_end = london_session_window(ref_date)
    hi_c = _extreme_in_window(candles, ls_start, ls_end, "HIGH")
    lo_c = _extreme_in_window(candles, ls_start, ls_end, "LOW")
    if hi_c:
        pools.append(LiquidityPool(instrument, PoolType.LONDON_HIGH, hi_c.high, ls_end, hi_c.open_time))
    if lo_c:
        pools.append(LiquidityPool(instrument, PoolType.LONDON_LOW, lo_c.low, ls_end, lo_c.open_time))

    lkz_start, lkz_end = kill_zone_bounds(SessionEnum.LONDON_KZ, ref_date)
    hi_c = _extreme_in_window(candles, lkz_start, lkz_end, "HIGH")
    lo_c = _extreme_in_window(candles, lkz_start, lkz_end, "LOW")
    if hi_c:
        pools.append(LiquidityPool(instrument, PoolType.LKZ_HIGH, hi_c.high, lkz_end, hi_c.open_time))
    if lo_c:
        pools.append(LiquidityPool(instrument, PoolType.LKZ_LOW, lo_c.low, lkz_end, lo_c.open_time))

    return pools


def find_equal_level_pools(
    swings: List[SwingPoint],
    instrument: Instrument,
    tolerance: float,
    min_candle_gap: int,
) -> List[LiquidityPool]:
    """1.5 — equal highs/lows: 2+ swing points within tolerance, >= min_candle_gap apart."""
    if not swings:
        return []
    kind = swings[0].kind
    pool_type = PoolType.EQUAL_HIGHS if kind == "HIGH" else PoolType.EQUAL_LOWS
    sorted_swings = sorted(swings, key=lambda s: s.candle_index)
    used: set = set()
    pools: List[LiquidityPool] = []
    for i, s1 in enumerate(sorted_swings):
        if s1.candle_index in used:
            continue
        cluster = [s1]
        for s2 in sorted_swings[i + 1:]:
            if s2.candle_index in used:
                continue
            if (
                abs(s2.price - s1.price) <= tolerance
                and abs(s2.candle_index - s1.candle_index) >= min_candle_gap
            ):
                cluster.append(s2)
        if len(cluster) >= 2:
            for s in cluster:
                used.add(s.candle_index)
            avg_price = sum(s.price for s in cluster) / len(cluster)
            pools.append(
                LiquidityPool(
                    instrument=instrument,
                    pool_type=pool_type,
                    price=avg_price,
                    formed_time=cluster[-1].confirmed_time,
                    oldest_touch_time=cluster[0].confirmed_time,
                )
            )
    return pools


def build_all_pools(
    candles: List[Candle],
    swing_highs: List[SwingPoint],
    swing_lows: List[SwingPoint],
    instrument: Instrument,
    inst_constants: InstrumentConstants,
    ref_date: datetime,
) -> List[LiquidityPool]:
    pools = build_session_pools(candles, instrument, ref_date)
    pools += find_equal_level_pools(
        swing_highs, instrument, inst_constants.equal_level_tolerance, inst_constants.equal_level_min_candle_gap
    )
    pools += find_equal_level_pools(
        swing_lows, instrument, inst_constants.equal_level_tolerance, inst_constants.equal_level_min_candle_gap
    )
    return pools


def find_target_pools(pools: List[LiquidityPool], direction) -> List[LiquidityPool]:
    """Pools on the target side of a trade: HIGH-type pools for LONG,
    LOW-type pools for SHORT — used by F7 target quality and TP/runner
    construction (Section 6)."""
    from ..core.enums import Direction

    types = HIGH_POOL_TYPES if direction == Direction.LONG else LOW_POOL_TYPES
    return [p for p in pools if p.pool_type in types]


def nearest_target_pool(pools: List[LiquidityPool], entry_price: float, direction) -> Optional[LiquidityPool]:
    from ..core.enums import Direction

    candidates = find_target_pools(pools, direction)
    if direction == Direction.LONG:
        ahead = [p for p in candidates if p.price > entry_price]
        return min(ahead, key=lambda p: p.price) if ahead else None
    ahead = [p for p in candidates if p.price < entry_price]
    return max(ahead, key=lambda p: p.price) if ahead else None


def detect_sweep(candles: List[Candle], pool: LiquidityPool, search_start_index: int = 0) -> Optional[Sweep]:
    """1.6 — price trades through the pool by any amount; a close-back on
    the original side within the sweeping candle or the next 3 M5 candles
    confirms a sweep. No close-back within that window = breakout, not a
    sweep, and this pool is decisively NOT a sweep from this breach.
    """
    is_low_pool = pool.pool_type in LOW_POOL_TYPES
    max_close_back = STRUCTURE.sweep_max_close_back_candles
    n = len(candles)

    for i in range(search_start_index, n):
        c = candles[i]
        traded_through = (c.low < pool.price) if is_low_pool else (c.high > pool.price)
        if not traded_through:
            continue

        extreme = c.low if is_low_pool else c.high
        for j in range(i, min(i + max_close_back + 1, n)):
            cj = candles[j]
            extreme = min(extreme, cj.low) if is_low_pool else max(extreme, cj.high)
            closed_back = (cj.close > pool.price) if is_low_pool else (cj.close < pool.price)
            if closed_back:
                return Sweep(
                    instrument=pool.instrument,
                    pool=pool,
                    sweep_candle_time=c.open_time,
                    sweep_candle_index=i,
                    sweep_extreme_price=extreme,
                    close_back_candle_time=cj.open_time,
                    close_back_candle_index=j,
                    candles_to_close_back=j - i,
                )
        return None  # breakout — the first breach is decisive per 1.6

    return None
