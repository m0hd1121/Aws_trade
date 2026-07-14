from __future__ import annotations

from datetime import datetime, timezone

from m5_reversal_bot.core.enums import Instrument, PoolType
from m5_reversal_bot.core.models import LiquidityPool
from m5_reversal_bot.strategy import liquidity

GMT = timezone.utc


def _pool(price=1.0000, pool_type=PoolType.ASIA_LOW):
    return LiquidityPool(
        instrument=Instrument.EURUSD, pool_type=pool_type, price=price,
        formed_time=datetime(2025, 1, 6, 6, 0, tzinfo=GMT), oldest_touch_time=datetime(2025, 1, 6, 2, 0, tzinfo=GMT),
    )


def test_sweep_confirmed_when_close_back_within_three_candles(builder):
    pool = _pool(price=1.0000, pool_type=PoolType.ASIA_LOW)
    builder.add_flat_run(3, 1.0010)             # pre-sweep noise, all above the pool
    builder.add(1.0005, 1.0006, 0.9995, 1.0002)  # sweeping candle: trades through 1.0000, closes back above
    candles = builder.build()

    sweep = liquidity.detect_sweep(candles, pool, search_start_index=0)
    assert sweep is not None
    assert sweep.sweep_candle_index == 3
    assert sweep.sweep_extreme_price == 0.9995
    assert sweep.candles_to_close_back == 0


def test_sweep_close_back_can_occur_up_to_three_candles_later(builder):
    pool = _pool(price=1.0000, pool_type=PoolType.ASIA_LOW)
    builder.add_flat_run(3, 1.0010)
    builder.add(1.0005, 1.0006, 0.9990, 0.9998)   # sweeps through, no close-back yet
    builder.add(0.9998, 0.9999, 0.9970, 0.9975)   # deeper wick, still below pool
    builder.add(0.9975, 1.0003, 0.9974, 1.0002)   # closes back above on the 3rd candle after the sweep
    candles = builder.build()

    sweep = liquidity.detect_sweep(candles, pool, search_start_index=0)
    assert sweep is not None
    assert sweep.sweep_extreme_price == 0.9970  # deepest wick across the whole liquidity grab
    assert sweep.candles_to_close_back == 2


def test_no_close_back_within_window_is_a_breakout_not_a_sweep(builder):
    pool = _pool(price=1.0000, pool_type=PoolType.ASIA_LOW)
    builder.add_flat_run(3, 1.0010)
    builder.add(1.0005, 1.0006, 0.9990, 0.9992)
    builder.add(0.9992, 0.9993, 0.9980, 0.9985)
    builder.add(0.9985, 0.9986, 0.9970, 0.9975)
    builder.add(0.9975, 0.9976, 0.9960, 0.9965)   # still below the pool 4 candles after the breach
    candles = builder.build()

    sweep = liquidity.detect_sweep(candles, pool, search_start_index=0)
    assert sweep is None


def test_equal_lows_pool_requires_min_candle_gap(builder):
    from m5_reversal_bot.strategy import structure

    # Two swing lows at the same price but only 3 candles apart -> should NOT cluster (needs >= 8).
    for i in range(20):
        low = 0.9900 if i in (5, 8) else 1.0000
        builder.add(1.0000, 1.0005, low, 1.0000)
    candles = builder.build()
    _, swing_lows = structure.find_all_swings(candles)
    pools = liquidity.find_equal_level_pools(swing_lows, Instrument.EURUSD, tolerance=0.00015, min_candle_gap=8)
    assert pools == []


def test_equal_lows_pool_forms_when_gap_and_tolerance_satisfied(builder):
    from m5_reversal_bot.strategy import structure

    for i in range(30):
        low = 0.99000 if i in (5, 20) else 1.0000
        builder.add(1.0000, 1.0005, low, 1.0000)
    candles = builder.build()
    _, swing_lows = structure.find_all_swings(candles)
    pools = liquidity.find_equal_level_pools(swing_lows, Instrument.EURUSD, tolerance=0.00015, min_candle_gap=8)
    assert len(pools) == 1
    assert pools[0].pool_type == PoolType.EQUAL_LOWS
