"""Section 4 — Entry Rules."""

from __future__ import annotations

from typing import Optional

from ..core.constants import ENTRY
from ..core.enums import Direction
from ..core.models import Candle, POI


def poi_far_edge(poi: POI, direction: Direction) -> float:
    """The edge of the POI furthest from the target — violating it means
    the reversal thesis inside this specific POI is dead before fill."""
    return poi.zone_low if direction == Direction.LONG else poi.zone_high


def is_poi_violated(candle: Candle, poi: POI, direction: Direction) -> bool:
    """4.2 — an M5 candle body CLOSE beyond the far edge of the POI."""
    if direction == Direction.LONG:
        return candle.close < poi.zone_low
    return candle.close > poi.zone_high


def missed_move_fraction(
    current_price: float, poi_entry_price: float, tp1_price: float, direction: Direction, baseline_price: float,
) -> float:
    """4.2 / 9(6) — fraction of the POI->TP1 distance price has run FURTHER
    away from the POI than it already was when the order was placed,
    without having filled.

    The order is placed "the moment the CHoCH candle closes" (4.1.1), and
    a CHoCH close is, by construction, already partway from the POI
    toward TP1 (Section 11.1's own numbers put it at ~46%). Measuring this
    rule from the raw POI price would cancel essentially every order the
    instant it's placed, which contradicts Example A's own successful
    fill after a retracement. The baseline is therefore the price at
    order placement (the CHoCH close); this rule fires only if price
    pushes on FURTHER beyond that point without ever retracing back for
    a fill — exactly the "the move is leaving" case the rule describes.
    Retracement back toward the POI always reads as 0 (never negative).
    """
    total = abs(tp1_price - poi_entry_price)
    if total == 0:
        return 0.0
    if direction == Direction.LONG:
        traveled_further = max(0.0, current_price - baseline_price)
    else:
        traveled_further = max(0.0, baseline_price - current_price)
    return traveled_further / total


def is_missed_move(
    current_price: float, poi_entry_price: float, tp1_price: float, direction: Direction, baseline_price: float,
) -> bool:
    return missed_move_fraction(current_price, poi_entry_price, tp1_price, direction, baseline_price) >= ENTRY.missed_move_fraction


def is_rejection_close(candle: Candle, direction: Direction) -> bool:
    """4.3 — body >= 50% of total range, in the trade direction."""
    if candle.body_close_fraction < ENTRY.rejection_close_min_body_fraction:
        return False
    return candle.is_bullish if direction == Direction.LONG else candle.is_bearish


def closes_inside_or_beyond_poi_toward_target(candle: Candle, poi: POI, direction: Direction) -> bool:
    """4.3 — closing inside or beyond the POI toward the target."""
    if direction == Direction.LONG:
        return candle.close >= poi.zone_low
    return candle.close <= poi.zone_high


def confirmation_entry_valid(candle: Candle, poi: POI, price_inside_poi: bool, direction: Direction) -> bool:
    """4.3 — alternate confirmation-market-entry test, used ONLY if the
    resting limit could not be placed before price returned to the POI."""
    if not price_inside_poi:
        return False
    if not closes_inside_or_beyond_poi_toward_target(candle, poi, direction):
        return False
    return is_rejection_close(candle, direction)
