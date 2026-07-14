"""Section 5 — Stop Loss (defined before entry, always)."""

from __future__ import annotations

from ..core.constants import InstrumentConstants
from ..core.enums import Direction
from ..core.models import Candle


def compute_buffer(current_spread: float, sweep_candle: Candle, inst_constants: InstrumentConstants) -> float:
    """5.2 — buffer = current spread + 15% of the sweep candle's total
    range, bounded by the instrument's floor/cap."""
    raw = current_spread + inst_constants.buffer_range_fraction * sweep_candle.range_size
    return min(max(raw, inst_constants.buffer_floor), inst_constants.buffer_cap)


def compute_stop_price(direction: Direction, sweep_extreme_price: float, buffer: float) -> float:
    """5.1 — long: below the sweep extreme low. short: above the sweep
    extreme high."""
    if direction == Direction.LONG:
        return sweep_extreme_price - buffer
    return sweep_extreme_price + buffer


def stop_distance(entry_price: float, stop_price: float) -> float:
    return abs(entry_price - stop_price)


def check_g2_stop_band(distance: float, inst_constants: InstrumentConstants) -> bool:
    """5.3 — Gate G2: total stop distance must fall inside the instrument's band."""
    return inst_constants.stop_distance_min <= distance <= inst_constants.stop_distance_max


def is_stop_widening(direction: Direction, current_stop: float, proposed_stop: float) -> bool:
    """5.4 — the stop is never widened; it may only move toward profit."""
    if direction == Direction.LONG:
        return proposed_stop < current_stop
    return proposed_stop > current_stop
