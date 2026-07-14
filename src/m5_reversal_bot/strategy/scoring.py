"""Section 3 — The Scoring Model. Computes F1-F10 objectively from already
detected structural facts; gates G1-G3 are set by the caller (engine.py)
since they depend on session/risk state this module doesn't own.
"""

from __future__ import annotations

from datetime import timedelta
from typing import List, Optional

from ..core.clock import kill_zone_bounds, minutes_between
from ..core.constants import SCORING, STRUCTURE
from ..core.enums import Direction, PoolType, Session
from ..core.models import CHoCH, Candle, DealingRange, FVG, Inducement, LiquidityPool, OrderBlock, POI, ScoreSheet, Sweep, SwingPoint
from . import structure as structure_mod
from .liquidity import nearest_target_pool
from .poi import poi_in_correct_zone

SENIOR_POOL_TYPES = {
    PoolType.ASIA_HIGH, PoolType.ASIA_LOW,
    PoolType.PDH, PoolType.PDL,
    PoolType.PWH, PoolType.PWL,
    PoolType.EQUAL_HIGHS, PoolType.EQUAL_LOWS,
}

NARRATIVE_LKZ_SOURCES = {PoolType.ASIA_HIGH, PoolType.ASIA_LOW}
NARRATIVE_NYKZ_SOURCES = {
    PoolType.LONDON_HIGH, PoolType.LONDON_LOW,
    PoolType.LKZ_HIGH, PoolType.LKZ_LOW,
    PoolType.PDH, PoolType.PDL,
}


def compute_h1_bias(h1_candles: List[Candle]) -> Optional[Direction]:
    """F1 — most recent confirmed H1 structure break (body close beyond an
    H1 5-candle-fractal swing)."""
    highs, lows = structure_mod.find_all_swings(h1_candles)
    lb = STRUCTURE.swing_fractal_lookback
    up_events = structure_mod.detect_bos_events_since(h1_candles, lb, Direction.LONG, highs)
    down_events = structure_mod.detect_bos_events_since(h1_candles, lb, Direction.SHORT, lows)
    combined = [(i, Direction.LONG) for i, _ in up_events] + [(i, Direction.SHORT) for i, _ in down_events]
    if not combined:
        return None
    combined.sort(key=lambda x: x[0])
    return combined[-1][1]


def score_f1(h1_bias: Optional[Direction], intended_direction: Direction) -> tuple:
    if h1_bias == intended_direction:
        return SCORING.weight_f1_htf_bias, "H1 bias aligned"
    return 0, f"H1 bias is {h1_bias}, trade direction is {intended_direction}"


def score_f2(sweep: Optional[Sweep], session: Session, ref_date) -> tuple:
    if sweep is None:
        return 0, "no qualified sweep"
    kz_start, kz_end = kill_zone_bounds(session, ref_date)
    window_start = kz_start - timedelta(minutes=60)
    if window_start <= sweep.sweep_candle_time <= kz_end:
        return SCORING.weight_f2_qualified_sweep, "sweep within KZ or preceding 60 minutes"
    return 0, "sweep outside the KZ/60-min pre-window"


def score_f3(sweep: Optional[Sweep], choch: Optional[CHoCH]) -> tuple:
    if sweep is None or choch is None:
        return 0, "no CHoCH confirmed"
    delta = choch.confirm_candle_index - sweep.sweep_candle_index
    if 0 <= delta <= STRUCTURE.choch_max_candles_from_sweep:
        return SCORING.weight_f3_m5_choch, f"CHoCH confirmed {delta} candles after sweep extreme"
    return 0, f"CHoCH confirmed {delta} candles after sweep — exceeds {STRUCTURE.choch_max_candles_from_sweep}"


def score_f4(displacement_found: bool) -> tuple:
    return (SCORING.weight_f4_displacement_fvg, "displacement + FVG present") if displacement_found else (0, "no qualifying displacement/FVG")


def score_f5(poi: Optional[POI], dealing_range: Optional[DealingRange], direction: Direction, mitigated: bool) -> tuple:
    if poi is None or dealing_range is None:
        return 0, "no POI"
    if mitigated:
        return 0, "POI already mitigated"
    if poi_in_correct_zone(poi, dealing_range, direction):
        return SCORING.weight_f5_poi_correct_zone, "unmitigated POI in correct discount/premium zone"
    return 0, "POI entry price outside discount/premium zone"


def score_f6(inducement: Optional[Inducement]) -> tuple:
    return (SCORING.weight_f6_inducement, "inducement swing present") if inducement else (0, "no inducement swing")


def score_f7(entry_price: float, stop_distance: float, pools: List[LiquidityPool], direction: Direction) -> tuple:
    target = nearest_target_pool(pools, entry_price, direction)
    if target is None or stop_distance <= 0:
        return 0, "no qualified opposing liquidity pool found"
    distance = abs(target.price - entry_price)
    r_multiple = distance / stop_distance
    if r_multiple >= SCORING.target_quality_min_r:
        return SCORING.weight_f7_target_quality, f"target {r_multiple:.2f}R to {target.pool_type.value}"
    return 0, f"target only {r_multiple:.2f}R — below {SCORING.target_quality_min_r}R minimum"


def score_f8(sweep: Optional[Sweep]) -> tuple:
    if sweep is None:
        return 0, "no sweep"
    if sweep.pool.pool_type not in SENIOR_POOL_TYPES:
        return 0, f"{sweep.pool.pool_type.value} is not a seniority-qualifying pool type"
    age_hours = (sweep.sweep_candle_time - sweep.pool.oldest_touch_time).total_seconds() / 3600.0
    if age_hours >= SCORING.pool_seniority_min_age_hours:
        return SCORING.weight_f8_pool_seniority, f"pool oldest touch {age_hours:.1f}h old"
    return 0, f"pool oldest touch only {age_hours:.1f}h old — below {SCORING.pool_seniority_min_age_hours}h"


def score_f9(smt_present: bool) -> tuple:
    return (SCORING.weight_f9_smt_divergence, "SMT divergence present") if smt_present else (0, "no SMT divergence")


def score_f10(session: Session, sweep: Optional[Sweep]) -> tuple:
    if sweep is None:
        return 0, "no sweep"
    pt = sweep.pool.pool_type
    if session == Session.LONDON_KZ and pt in NARRATIVE_LKZ_SOURCES:
        return SCORING.weight_f10_session_narrative, "LKZ trade sweeping the Asia extreme"
    if session == Session.NEWYORK_KZ and pt in NARRATIVE_NYKZ_SOURCES:
        return SCORING.weight_f10_session_narrative, "NYKZ trade sweeping London/LKZ extreme or PDH/PDL"
    return 0, f"{pt.value} sweep does not match the {session.value} narrative"


def build_score_sheet(
    *,
    h1_bias: Optional[Direction],
    direction: Direction,
    sweep: Optional[Sweep],
    choch: Optional[CHoCH],
    displacement_found: bool,
    poi: Optional[POI],
    dealing_range: Optional[DealingRange],
    poi_mitigated: bool,
    inducement: Optional[Inducement],
    entry_price: Optional[float],
    stop_distance: Optional[float],
    all_pools: List[LiquidityPool],
    smt_present: bool,
    session: Session,
    ref_date,
) -> ScoreSheet:
    sheet = ScoreSheet()
    sheet.f1_htf_bias, sheet.reasons["F1"] = score_f1(h1_bias, direction)
    sheet.f2_qualified_sweep, sheet.reasons["F2"] = score_f2(sweep, session, ref_date)
    sheet.f3_m5_choch, sheet.reasons["F3"] = score_f3(sweep, choch)
    sheet.f4_displacement_fvg, sheet.reasons["F4"] = score_f4(displacement_found)
    sheet.f5_poi_correct_zone, sheet.reasons["F5"] = score_f5(poi, dealing_range, direction, poi_mitigated)
    sheet.f6_inducement, sheet.reasons["F6"] = score_f6(inducement)
    if entry_price is not None and stop_distance is not None:
        sheet.f7_target_quality, sheet.reasons["F7"] = score_f7(entry_price, stop_distance, all_pools, direction)
    else:
        sheet.f7_target_quality, sheet.reasons["F7"] = 0, "stop/entry not yet constructed"
    sheet.f8_pool_seniority, sheet.reasons["F8"] = score_f8(sweep)
    sheet.f9_smt_divergence, sheet.reasons["F9"] = score_f9(smt_present)
    sheet.f10_session_narrative, sheet.reasons["F10"] = score_f10(session, sweep)
    return sheet
