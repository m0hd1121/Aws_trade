from __future__ import annotations

from m5_reversal_bot.core.enums import Instrument
from m5_reversal_bot.strategy import risk


def test_position_sizing_eu_worked_example_8_1():
    # "EU example: equity $10,000, risk 1%, stop 8.0 pips -> $100 / (8 *
    # $10/pip per standard lot) = 1.25" per Section 8.1's literal formula.
    size = risk.compute_position_size(
        equity=10_000, risk_percent=1.0, stop_distance_price=8.0 * 0.0001, instrument=Instrument.EURUSD, lot_step=0.01,
    )
    assert size == 1.25


def test_position_sizing_xau_worked_example_8_1():
    # "XAU example: equity $10,000, risk 1%, stop $4.00 -> $100 / ($4.00 *
    # $100 per 1-lot per $1) = 0.25 lots."
    size = risk.compute_position_size(
        equity=10_000, risk_percent=1.0, stop_distance_price=4.00, instrument=Instrument.XAUUSD, lot_step=0.01,
    )
    assert size == 0.25


def test_position_size_rounds_down_never_up():
    # stop distance chosen so the raw division doesn't land on a clean step.
    size = risk.compute_position_size(
        equity=10_000, risk_percent=1.0, stop_distance_price=7.3 * 0.0001, instrument=Instrument.EURUSD, lot_step=0.01,
    )
    raw = (10_000 * 0.01) / (7.3 * 10.0)
    assert size <= raw
    assert round(size, 2) == size


def test_determine_risk_percent_evaluation_phase():
    snap = risk.AccountSnapshot(
        equity_start_of_day=10_000, equity_current=10_000, high_water_mark_month=10_000,
        daily_realized_loss_percent=0, weekly_realized_loss_percent=0,
        consecutive_losses_this_session=0, consecutive_losses_running=0,
        trades_this_kill_zone=0, trades_today=0, concurrent_positions_total=0,
        concurrent_positions_by_instrument={}, combined_open_risk_percent=0,
        live_trades_taken_lifetime=10, in_recovery_mode=False, monthly_drawdown_percent=0,
        monthly_brake_active=False, demo_requalification_trades_done=0,
    )
    assert risk.determine_risk_percent(snap) == 0.5  # < 40 live trades -> evaluation phase


def test_determine_risk_percent_normal_after_evaluation():
    snap = risk.AccountSnapshot(
        equity_start_of_day=10_000, equity_current=10_000, high_water_mark_month=10_000,
        daily_realized_loss_percent=0, weekly_realized_loss_percent=0,
        consecutive_losses_this_session=0, consecutive_losses_running=0,
        trades_this_kill_zone=0, trades_today=0, concurrent_positions_total=0,
        concurrent_positions_by_instrument={}, combined_open_risk_percent=0,
        live_trades_taken_lifetime=41, in_recovery_mode=False, monthly_drawdown_percent=0,
        monthly_brake_active=False, demo_requalification_trades_done=0,
    )
    assert risk.determine_risk_percent(snap) == 1.0


def test_g3_blocks_on_daily_loss_limit():
    snap = risk.AccountSnapshot(
        equity_start_of_day=10_000, equity_current=9_800, high_water_mark_month=10_000,
        daily_realized_loss_percent=2.0, weekly_realized_loss_percent=0,
        consecutive_losses_this_session=0, consecutive_losses_running=0,
        trades_this_kill_zone=0, trades_today=2, concurrent_positions_total=0,
        concurrent_positions_by_instrument={}, combined_open_risk_percent=0,
        live_trades_taken_lifetime=41, in_recovery_mode=False, monthly_drawdown_percent=0,
        monthly_brake_active=False, demo_requalification_trades_done=0,
    )
    decision = risk.evaluate_g3(snap, Instrument.EURUSD, proposed_risk_percent=1.0)
    assert decision.g3_pass is False
    assert any("daily loss" in r for r in decision.blocked_reasons)


def test_g3_combined_risk_limit_for_simultaneous_eu_xau():
    snap = risk.AccountSnapshot(
        equity_start_of_day=10_000, equity_current=10_000, high_water_mark_month=10_000,
        daily_realized_loss_percent=0, weekly_realized_loss_percent=0,
        consecutive_losses_this_session=0, consecutive_losses_running=0,
        trades_this_kill_zone=0, trades_today=1, concurrent_positions_total=1,
        concurrent_positions_by_instrument={Instrument.EURUSD: 1}, combined_open_risk_percent=1.0,
        live_trades_taken_lifetime=41, in_recovery_mode=False, monthly_drawdown_percent=0,
        monthly_brake_active=False, demo_requalification_trades_done=0,
    )
    # Adding another 1% risk on XAU would push combined risk to 2.0% > 1.5% cap.
    decision = risk.evaluate_g3(snap, Instrument.XAUUSD, proposed_risk_percent=1.0)
    assert decision.g3_pass is False


def test_monthly_brake_fires_at_minus_6_percent_from_hwm():
    assert risk.check_monthly_brake(equity_current=9_400, high_water_mark_month=10_000) is True
    assert risk.check_monthly_brake(equity_current=9_500, high_water_mark_month=10_000) is False
