"""Definition 1.10 (POI), 1.11 (Dealing Range / discount / premium).

See Section 11.1 (Example A) for the one nuance this module encodes
explicitly: 4.1.2 places the resting limit at "the level that defines the
scored POI." The FVG is primary by 1.10, but if its CE fails the
discount/premium test (F5) while the leg's Order Block midpoint *does*
sit in the correct zone, the system takes the compliant OB level instead
of forcing a non-compliant FVG entry — the deeper POI qualifies. If
neither is compliant, the FVG remains primary and F5 will simply score 0.
"""

from __future__ import annotations

from typing import Optional

from ..core.enums import Direction, POISource
from ..core.models import CHoCH, DealingRange, FVG, OrderBlock, POI, Sweep


def build_dealing_range(sweep: Sweep, choch: CHoCH) -> DealingRange:
    """1.11 — sweep extreme (0%) to CHoCH confirmation close (100%). Stored
    geometrically as [low, high]; `in_discount`/`in_premium` on
    `DealingRange` then correctly resolve to "the half nearer the sweep
    extreme" for both LONG and SHORT because of how low/high fall out here.
    """
    lo = min(sweep.sweep_extreme_price, choch.close_price)
    hi = max(sweep.sweep_extreme_price, choch.close_price)
    return DealingRange(low=lo, high=hi)


def build_poi(
    fvg: Optional[FVG],
    ob: Optional[OrderBlock],
    dealing_range: DealingRange,
    direction: Direction,
) -> Optional[POI]:
    if fvg is None and ob is None:
        return None

    def in_correct_zone(price: float) -> bool:
        return dealing_range.in_discount(price) if direction == Direction.LONG else dealing_range.in_premium(price)

    # Base zone per 1.10: overlap if both exist and overlap, else FVG primary.
    if fvg and ob:
        overlap_low, overlap_high = max(fvg.gap_low, ob.low), min(fvg.gap_high, ob.high)
        if overlap_low < overlap_high:
            base_zone_low, base_zone_high, base_source = overlap_low, overlap_high, POISource.FVG_OB_OVERLAP
        else:
            base_zone_low, base_zone_high, base_source = fvg.gap_low, fvg.gap_high, POISource.FVG
    elif fvg:
        base_zone_low, base_zone_high, base_source = fvg.gap_low, fvg.gap_high, POISource.FVG
    else:
        base_zone_low, base_zone_high, base_source = ob.low, ob.high, POISource.ORDER_BLOCK

    fvg_entry = fvg.ce if fvg else None
    ob_entry = ob.midpoint if ob else None

    # 4.1.2 entry construction, with the Example-A compliance nuance.
    if fvg_entry is not None and in_correct_zone(fvg_entry):
        entry_price, zone_low, zone_high, source = fvg_entry, base_zone_low, base_zone_high, base_source
    elif ob_entry is not None and in_correct_zone(ob_entry):
        entry_price, zone_low, zone_high, source = ob_entry, ob.low, ob.high, POISource.ORDER_BLOCK
    elif fvg_entry is not None:
        entry_price, zone_low, zone_high, source = fvg_entry, base_zone_low, base_zone_high, base_source
    elif ob_entry is not None:
        entry_price, zone_low, zone_high, source = ob_entry, ob.low, ob.high, POISource.ORDER_BLOCK
    else:
        return None

    instrument = (fvg.instrument if fvg else ob.instrument)
    return POI(
        instrument=instrument,
        direction=direction,
        source=source,
        zone_low=zone_low,
        zone_high=zone_high,
        entry_price=entry_price,
        fvg=fvg,
        order_block=ob,
    )


def poi_in_correct_zone(poi: POI, dealing_range: DealingRange, direction: Direction) -> bool:
    """F5 — unmitigated POI whose entry price sits in discount (longs) /
    premium (shorts). Mitigation is checked separately (order_block.py /
    engine.py, since FVGs and OBs mitigate differently)."""
    if direction == Direction.LONG:
        return dealing_range.in_discount(poi.entry_price)
    return dealing_range.in_premium(poi.entry_price)


def is_fvg_mitigated(candles, fvg: FVG, since_index: int) -> bool:
    """An FVG is mitigated once price trades back through the gap."""
    for c in candles[since_index:]:
        if c.low <= fvg.gap_high and c.high >= fvg.gap_low:
            return True
    return False
