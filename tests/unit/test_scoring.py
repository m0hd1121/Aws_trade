from __future__ import annotations

from m5_reversal_bot.core.models import ScoreSheet


def test_decision_rule_requires_score_9_and_full_spine_and_all_gates():
    sheet = ScoreSheet(
        f1_htf_bias=2, f2_qualified_sweep=2, f3_m5_choch=2, f4_displacement_fvg=1,
        f5_poi_correct_zone=1, f6_inducement=1, f7_target_quality=1, f8_pool_seniority=1,
        f9_smt_divergence=1, f10_session_narrative=0,
        g1_time_and_disqualifiers=True, g2_stop_distance_band=True, g3_account_risk_limits=True,
    )
    assert sheet.total == 12
    assert sheet.spine_full is True
    assert sheet.authorized is True


def test_score_all_factors_full_is_authorized_example_a():
    # Note: the rulebook's own per-factor weights (2+2+2+1x7) sum to 13,
    # not the "12 points available" the prose states elsewhere — see the
    # comment on ScoringConstants.max_score. The literal sum of the
    # weights as given is what this asserts.
    sheet = ScoreSheet(
        f1_htf_bias=2, f2_qualified_sweep=2, f3_m5_choch=2, f4_displacement_fvg=1,
        f5_poi_correct_zone=1, f6_inducement=1, f7_target_quality=1, f8_pool_seniority=1,
        f9_smt_divergence=1, f10_session_narrative=1,
        g1_time_and_disqualifiers=True, g2_stop_distance_band=True, g3_account_risk_limits=True,
    )
    assert sheet.total == 13
    assert sheet.authorized is True


def test_example_b_rejected_for_broken_spine_despite_high_score():
    # Section 11.2 — 8/12, and F1 (HTF bias) = 0: counter-trend short with
    # no displacement. Fails twice: under 9, and the spine isn't full.
    sheet = ScoreSheet(
        f1_htf_bias=0, f2_qualified_sweep=2, f3_m5_choch=2, f4_displacement_fvg=0,
        f5_poi_correct_zone=1, f6_inducement=0, f7_target_quality=1, f8_pool_seniority=1,
        f9_smt_divergence=0, f10_session_narrative=1,
        g1_time_and_disqualifiers=True, g2_stop_distance_band=True, g3_account_risk_limits=True,
    )
    assert sheet.total == 8
    assert sheet.spine_full is False
    assert sheet.authorized is False


def test_score_9_but_spine_broken_is_not_authorized():
    # A 9-built-without-the-spine is explicitly "a different trade, not
    # this system's trade" per Section 3.
    sheet = ScoreSheet(
        f1_htf_bias=0, f2_qualified_sweep=2, f3_m5_choch=2, f4_displacement_fvg=1,
        f5_poi_correct_zone=1, f6_inducement=1, f7_target_quality=1, f8_pool_seniority=1,
        f9_smt_divergence=0, f10_session_narrative=0,
        g1_time_and_disqualifiers=True, g2_stop_distance_band=True, g3_account_risk_limits=True,
    )
    assert sheet.total == 9
    assert sheet.spine_full is False
    assert sheet.authorized is False


def test_gate_failure_blocks_trade_even_at_max_score():
    sheet = ScoreSheet(
        f1_htf_bias=2, f2_qualified_sweep=2, f3_m5_choch=2, f4_displacement_fvg=1,
        f5_poi_correct_zone=1, f6_inducement=1, f7_target_quality=1, f8_pool_seniority=1,
        f9_smt_divergence=1, f10_session_narrative=1,
        g1_time_and_disqualifiers=True, g2_stop_distance_band=False, g3_account_risk_limits=True,
    )
    assert sheet.total == 13
    assert sheet.spine_full is True
    assert sheet.authorized is False  # G2 (stop band) failed
