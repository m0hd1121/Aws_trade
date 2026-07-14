from __future__ import annotations

from datetime import datetime, timezone

from m5_reversal_bot.core.constants import EU, XAU
from m5_reversal_bot.core.enums import Direction, Instrument
from m5_reversal_bot.strategy import stop_loss
from tests.conftest import make_candle

GMT = timezone.utc


def test_buffer_matches_worked_example_a():
    # Section 11.1: sweep candle range 11 pips, spread 0.7 pips ->
    # buffer = 0.7 + 15%*11 = 2.35 pips, inside the 1.5-4.0 pip cap.
    sweep_candle = make_candle(Instrument.EURUSD, "M5", datetime(2025, 1, 6, 7, 35, tzinfo=GMT),
                                1.08385, 1.08385 + 0.0011, 1.08385, 1.08455)
    buffer = stop_loss.compute_buffer(current_spread=0.00007, sweep_candle=sweep_candle, inst_constants=EU)
    assert round(buffer, 6) == round(0.00007 + 0.15 * 0.0011, 6)
    assert EU.buffer_floor <= buffer <= EU.buffer_cap

    stop_price = stop_loss.compute_stop_price(Direction.LONG, sweep_extreme_price=1.08385, buffer=buffer)
    assert round(stop_price, 5) == round(1.08385 - buffer, 5)

    entry_price = 1.08458  # OB 50% level per the worked example
    distance = stop_loss.stop_distance(entry_price, stop_price)
    distance_pips = distance / EU.pip_value_in_price
    assert 9.0 <= distance_pips <= 10.0  # rulebook narrative: "9.7 pips"
    assert stop_loss.check_g2_stop_band(distance, EU) is True


def test_buffer_respects_floor_and_cap():
    tiny_range_candle = make_candle(Instrument.EURUSD, "M5", datetime(2025, 1, 6, 7, 35, tzinfo=GMT),
                                     1.0000, 1.00005, 0.99995, 1.0000)
    buffer = stop_loss.compute_buffer(current_spread=0.0, sweep_candle=tiny_range_candle, inst_constants=EU)
    assert buffer == EU.buffer_floor

    huge_range_candle = make_candle(Instrument.EURUSD, "M5", datetime(2025, 1, 6, 7, 35, tzinfo=GMT),
                                     1.0000, 1.0100, 0.9900, 1.0000)
    buffer = stop_loss.compute_buffer(current_spread=0.0, sweep_candle=huge_range_candle, inst_constants=EU)
    assert buffer == EU.buffer_cap


def test_g2_band_xau():
    assert stop_loss.check_g2_stop_band(2.50, XAU) is True
    assert stop_loss.check_g2_stop_band(9.00, XAU) is True
    assert stop_loss.check_g2_stop_band(2.49, XAU) is False
    assert stop_loss.check_g2_stop_band(9.01, XAU) is False


def test_stop_never_widens():
    assert stop_loss.is_stop_widening(Direction.LONG, current_stop=1.0800, proposed_stop=1.0795) is True
    assert stop_loss.is_stop_widening(Direction.LONG, current_stop=1.0800, proposed_stop=1.0810) is False
    assert stop_loss.is_stop_widening(Direction.SHORT, current_stop=1.0800, proposed_stop=1.0805) is True
    assert stop_loss.is_stop_widening(Direction.SHORT, current_stop=1.0800, proposed_stop=1.0790) is False
