from __future__ import annotations

from datetime import datetime, timezone

import pytest

from m5_reversal_bot.core.constants import EU
from m5_reversal_bot.core.enums import Direction, Instrument, PoolType
from m5_reversal_bot.core.models import LiquidityPool
from m5_reversal_bot.strategy import exits

GMT = timezone.utc


def _pool(price, pool_type):
    return LiquidityPool(
        instrument=Instrument.EURUSD, pool_type=pool_type, price=price,
        formed_time=datetime(2025, 1, 6, 6, 0, tzinfo=GMT), oldest_touch_time=datetime(2025, 1, 6, 2, 0, tzinfo=GMT),
    )


def test_tp1_uses_pool_between_2r_and_2_5r_fronted_by_2_pips():
    # Section 11.1: entry 1.08458, stop distance 9.7 pips, Asia high pool at
    # 1.0870 sits at 2.49R -> TP1 = 1.0870 - 2 pips = 1.08680.
    entry_price = 1.08458
    stop_distance = 0.00097  # 9.7 pips
    pools = [_pool(1.08700, PoolType.ASIA_HIGH)]
    tp1_price, r_multiple, pool_used = exits.compute_tp1(entry_price, stop_distance, Direction.LONG, pools, EU)
    assert round(tp1_price, 5) == 1.08680
    assert pool_used is not None
    assert 2.0 <= r_multiple <= 2.5


def test_tp1_falls_back_to_fixed_2r_when_no_pool_in_window():
    entry_price = 1.08458
    stop_distance = 0.00097
    tp1_price, r_multiple, pool_used = exits.compute_tp1(entry_price, stop_distance, Direction.LONG, [], EU)
    assert pool_used is None
    assert r_multiple == 2.0
    assert round(tp1_price, 5) == round(entry_price + 2 * stop_distance, 5)


def test_runner_target_is_next_pool_beyond_tp1_fronted():
    # Section 11.1: TP1 was built from the Asia-high pool (1.08700); the
    # runner must target the NEXT pool beyond that — PDH at 1.08925,
    # fronted 2 pips -> 1.08905 — not re-target the same Asia-high pool
    # just because 1.08700 > tp1_price(1.08680).
    asia_high = _pool(1.08700, PoolType.ASIA_HIGH)
    pdh = _pool(1.08925, PoolType.PDH)
    target = exits.compute_runner_target(
        entry_price=1.08458, tp1_price=1.08680, direction=Direction.LONG,
        pools=[asia_high, pdh], inst_constants=EU, tp1_pool=asia_high,
    )
    assert round(target, 5) == 1.08905


def test_breakeven_only_applies_entry_plus_costs():
    be = exits.breakeven_stop(Direction.LONG, entry_price=1.08458, spread=0.00007, commission_equivalent=0.0)
    assert round(be, 5) == round(1.08458 + 0.00007, 5)
    be_short = exits.breakeven_stop(Direction.SHORT, entry_price=1.08458, spread=0.00007)
    assert round(be_short, 5) == round(1.08458 - 0.00007, 5)


def test_r_multiple_sign_convention():
    assert exits.r_multiple(Direction.LONG, entry_price=1.0800, exit_price=1.0850, stop_distance=0.0025) == pytest.approx(2.0)
    assert exits.r_multiple(Direction.LONG, entry_price=1.0800, exit_price=1.0775, stop_distance=0.0025) == pytest.approx(-1.0)
    assert exits.r_multiple(Direction.SHORT, entry_price=1.0800, exit_price=1.0750, stop_distance=0.0025) == pytest.approx(2.0)
