"""Section 9 — Absolute Filters (no trade regardless of score).

Most of these nine filters are the direct output of another module
(chop.py, sessions.py D1-D7, stop_loss.py G2, entry.py's missed-move test,
risk.py's G3). This module supplies the two filters with no other home
(#5 structure-quality, #9 platform/connectivity) and the combinator that
merges all nine into one authorization-blocking report, so `engine.py` has
a single place to ask "is any absolute filter tripped?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ..core.constants import STRUCTURE_QUALITY
from ..core.models import Candle, CHoCH, DealingRange, Sweep


def is_structure_quality_filtered(sweep: Sweep, choch: CHoCH, dealing_range: DealingRange, sweep_candle: Candle) -> bool:
    """9.5 — the sweep candle itself IS the CHoCH candle AND its total
    range exceeds 60% of the entire dealing range: no meaningful POI would
    exist, entry would be mid-candle noise."""
    if sweep.sweep_candle_time != choch.confirm_candle_time:
        return False
    total_range = dealing_range.high - dealing_range.low
    if total_range <= 0:
        return False
    return sweep_candle.range_size > STRUCTURE_QUALITY.max_single_candle_dealing_range_fraction * total_range


def is_platform_connectivity_filtered(bracket_order_supported_atomically: bool) -> bool:
    """9.9 — if the full bracket (entry+SL+TP) cannot be placed in one
    action, no trade."""
    return not bracket_order_supported_atomically


@dataclass
class AbsoluteFiltersReport:
    chop_filter: bool = False
    news_blackout_filter: bool = False
    spread_filter: bool = False
    stop_band_filter: bool = False
    structure_quality_filter: bool = False
    missed_move_filter: bool = False
    account_state_filter: bool = False
    session_disqualifier_filter: bool = False
    platform_connectivity_filter: bool = False
    reasons: List[str] = field(default_factory=list)

    @property
    def any_triggered(self) -> bool:
        return any(
            [
                self.chop_filter,
                self.news_blackout_filter,
                self.spread_filter,
                self.stop_band_filter,
                self.structure_quality_filter,
                self.missed_move_filter,
                self.account_state_filter,
                self.session_disqualifier_filter,
                self.platform_connectivity_filter,
            ]
        )


def evaluate_absolute_filters(
    *,
    chop: bool,
    news_blackout: bool,
    spread_breach: bool,
    stop_band_breach: bool,
    structure_quality_breach: bool,
    missed_move: bool,
    account_state_breach: bool,
    session_disqualifier: bool,
    platform_connectivity_breach: bool,
) -> AbsoluteFiltersReport:
    report = AbsoluteFiltersReport(
        chop_filter=chop,
        news_blackout_filter=news_blackout,
        spread_filter=spread_breach,
        stop_band_filter=stop_band_breach,
        structure_quality_filter=structure_quality_breach,
        missed_move_filter=missed_move,
        account_state_filter=account_state_breach,
        session_disqualifier_filter=session_disqualifier,
        platform_connectivity_filter=platform_connectivity_breach,
    )
    label_map = {
        "chop_filter": "1. Chop filter (1.14)",
        "news_blackout_filter": "2. News blackout (D1/D2)",
        "spread_filter": "3. Spread filter (D7)",
        "stop_band_filter": "4. Stop-band filter (G2)",
        "structure_quality_filter": "5. Structure-quality filter (9.5)",
        "missed_move_filter": "6. Missed-move filter (4.2c)",
        "account_state_filter": "7. Account-state filter (Section 8)",
        "session_disqualifier_filter": "8. Session disqualifiers (D3-D6)",
        "platform_connectivity_filter": "9. Platform/connectivity filter (9.9)",
    }
    for attr, label in label_map.items():
        if getattr(report, attr):
            report.reasons.append(label)
    return report
