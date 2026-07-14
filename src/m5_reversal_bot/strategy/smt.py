"""Definition 1.15 — SMT Divergence.

Binary check at sweep time: no interpretation. EUR/USD's reference is
GBP/USD; XAU/USD's reference is XAG/USD (or DXY inverse — the DXY-inverse
variant simply flips the breach direction since DXY moves opposite gold).
"""

from __future__ import annotations

from typing import List, Optional

from ..core.enums import Instrument, PoolType
from ..core.models import Candle, LiquidityPool, Sweep

REFERENCE_INSTRUMENT = {
    Instrument.EURUSD: "GBPUSD",
    Instrument.XAUUSD: "XAGUSD",
}

_LOW_TYPES = {PoolType.ASIA_LOW, PoolType.PDL, PoolType.PWL, PoolType.LONDON_LOW, PoolType.EQUAL_LOWS}


def check_smt_divergence(
    primary_sweep: Sweep,
    reference_candles: List[Candle],
    reference_equivalent_level: float,
    dxy_inverse: bool = False,
) -> bool:
    """Returns True if SMT divergence is present: at the moment the primary
    instrument swept its pool, the reference instrument's window did NOT
    breach its equivalent level.
    """
    is_low_pool = primary_sweep.pool.pool_type in _LOW_TYPES
    window = [
        c for c in reference_candles
        if primary_sweep.sweep_candle_time <= c.open_time <= primary_sweep.close_back_candle_time
    ]
    if not window:
        return False

    check_low = is_low_pool
    if dxy_inverse:
        check_low = not check_low  # DXY moves inverse to XAU/USD

    if check_low:
        breached = any(c.low < reference_equivalent_level for c in window)
    else:
        breached = any(c.high > reference_equivalent_level for c in window)
    return not breached


def find_reference_equivalent_level(
    reference_pools: List[LiquidityPool], primary_pool_type: PoolType
) -> Optional[float]:
    for p in reference_pools:
        if p.pool_type == primary_pool_type:
            return p.price
    return None
