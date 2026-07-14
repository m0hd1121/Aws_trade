"""Quarterly recalibration statistics — Section 2.5 note and Section 5.3.

The rulebook explicitly calls these two bands "a statistic computed
off-chart, not an indicator," to be recalibrated quarterly:
  - D3/D4 Asia-range disqualifier band: 20th/95th percentile of the last
    60 Asia ranges.
  - XAU G2 stop-distance band: recalibrated against the 60-day median
    NY-session range.

This module computes the statistics only. It never runs inside the live
decision path (`strategy/engine.py` always reads the frozen defaults in
`core/constants.py` unless an operator has explicitly published a new
calibration via `scripts/recalibrate_bands.py`, which writes a dated,
audited override file — see docs/STRATEGY_INTEGRITY.md). The METHOD is
frozen; only the resulting numbers move, and only offline, only quarterly.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass


def percentile(values: list, pct: float) -> float:
    if not values:
        raise ValueError("cannot compute a percentile of an empty series")
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


@dataclass(frozen=True)
class AsiaBandCalibration:
    min_range: float
    max_range: float
    sample_size: int


def recalibrate_asia_band(last_60_asia_ranges: list) -> AsiaBandCalibration:
    """D3/D4 — 20th percentile floor, 95th percentile cap, of the last 60
    Asia ranges. Requires at least 20 samples to be statistically meaningful."""
    if len(last_60_asia_ranges) < 20:
        raise ValueError("need at least 20 Asia-range samples to recalibrate D3/D4")
    p20 = percentile(last_60_asia_ranges, 20)
    p95 = percentile(last_60_asia_ranges, 95)
    return AsiaBandCalibration(min_range=p20, max_range=p95, sample_size=len(last_60_asia_ranges))


@dataclass(frozen=True)
class XAUStopBandCalibration:
    median_ny_range: float
    suggested_min: float
    suggested_max: float
    sample_size: int


def recalibrate_xau_stop_band(last_60day_ny_session_ranges: list) -> XAUStopBandCalibration:
    """5.3 — XAU G2 band recalibrated against the 60-day median NY-session
    range. The rulebook fixes the *method* (median-anchored) without
    prescribing a formula beyond that; this implementation keeps the
    existing band's proportions (floor ~28% / cap ~100% of the median
    range that produced the original $2.50-$9.00 band) so recalibration
    scales the band rather than redefining its shape.
    """
    if len(last_60day_ny_session_ranges) < 20:
        raise ValueError("need at least 20 daily NY-session range samples to recalibrate G2/XAU")
    median_range = statistics.median(last_60day_ny_session_ranges)
    # Original band (2.50-9.00) was calibrated against an assumed median
    # NY-session range of ~$9.00; preserve that ratio on recalibration.
    baseline_median = 9.00
    scale = median_range / baseline_median
    return XAUStopBandCalibration(
        median_ny_range=median_range,
        suggested_min=round(2.50 * scale, 2),
        suggested_max=round(9.00 * scale, 2),
        sample_size=len(last_60day_ny_session_ranges),
    )
