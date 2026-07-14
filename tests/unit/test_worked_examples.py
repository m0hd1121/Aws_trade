"""Encodes Section 11's three worked examples directly against the engine's
building blocks. The rulebook itself says prices are "illustrative to
demonstrate the mechanics; the arithmetic and rule application are exact"
— so these tests feed the exact numbers given in the document into the
exact functions that would have produced them, rather than trying to
reverse-engineer a full chart from prose.
"""

from __future__ import annotations

from datetime import datetime, timezone

from m5_reversal_bot.core.enums import Direction, Instrument
from m5_reversal_bot.core.models import CHoCH, DealingRange, FVG, OrderBlock, ScoreSheet, Sweep, SwingPoint, LiquidityPool, NewsEvent
from m5_reversal_bot.core.enums import PoolType
from m5_reversal_bot.strategy import poi as poi_mod
from m5_reversal_bot.strategy import sessions as sessions_mod

GMT = timezone.utc


# ---------------------------------------------------------------- Example A
def test_example_a_poi_falls_back_to_ob_when_fvg_ce_fails_discount():
    """Section 11.1: FVG CE (1.084875) sits marginally ABOVE the dealing
    range midpoint (1.084725), failing the discount test. The OB 50%
    (1.084575) is compliant, so 4.1.2 takes the OB level — "the system
    takes the compliant level, since 4.1.2 places the limit at the level
    that defines the scored POI." Final entry: 1.08458 (rulebook rounds).
    """
    fvg = FVG(
        instrument=Instrument.EURUSD, direction=Direction.LONG,
        candle1_time=datetime(2025, 1, 6, 7, 45, tzinfo=GMT), candle3_time=datetime(2025, 1, 6, 7, 55, tzinfo=GMT),
        gap_low=1.08470, gap_high=1.08505,
    )
    assert round(fvg.ce, 6) == 1.084875

    ob = OrderBlock(
        instrument=Instrument.EURUSD, direction=Direction.LONG,
        candle_time=datetime(2025, 1, 6, 7, 40, tzinfo=GMT), low=1.08440, high=1.08475,
    )
    assert round(ob.midpoint, 6) == 1.084575

    dealing_range = DealingRange(low=1.08385, high=1.08560)
    assert round(dealing_range.midpoint, 6) == 1.084725

    assert dealing_range.in_discount(fvg.ce) is False
    assert dealing_range.in_discount(ob.midpoint) is True

    resulting_poi = poi_mod.build_poi(fvg, ob, dealing_range, Direction.LONG)
    assert resulting_poi is not None
    assert round(resulting_poi.entry_price, 5) == 1.08458  # rulebook's rounded entry
    assert resulting_poi.order_block is ob


def test_example_a_score_sheet_has_full_spine_and_every_factor_lit():
    # See ScoringConstants.max_score: the rulebook's own per-factor
    # weights sum to 13 when every factor is full, though its prose
    # elsewhere says "12 points available" — a pre-existing inconsistency
    # in the source document. The weights themselves are transcribed
    # verbatim; what matters for authorization (>=9, spine full) holds.
    sheet = ScoreSheet(
        f1_htf_bias=2, f2_qualified_sweep=2, f3_m5_choch=2, f4_displacement_fvg=1,
        f5_poi_correct_zone=1, f6_inducement=1, f7_target_quality=1, f8_pool_seniority=1,
        f9_smt_divergence=1, f10_session_narrative=1,
        g1_time_and_disqualifiers=True, g2_stop_distance_band=True, g3_account_risk_limits=True,
    )
    assert sheet.total == 13
    assert sheet.authorized is True


# ---------------------------------------------------------------- Example B
def test_example_b_score_sheet_is_8_of_12_and_rejected():
    """Section 11.2: XAU/USD NY KZ short, F1=0 (counter H1-bullish),
    F4=0 (no qualifying displacement), F6=0 (no inducement), F9=0 (no
    SMT) -> 8/12, spine broken by F1. Rejected twice over: under 9, and
    the mandatory spine isn't full."""
    sheet = ScoreSheet(
        f1_htf_bias=0, f2_qualified_sweep=2, f3_m5_choch=2, f4_displacement_fvg=0,
        f5_poi_correct_zone=1, f6_inducement=0, f7_target_quality=1, f8_pool_seniority=1,
        f9_smt_divergence=0, f10_session_narrative=1,
        g1_time_and_disqualifiers=True, g2_stop_distance_band=True, g3_account_risk_limits=True,
    )
    assert sheet.total == 8
    assert sheet.spine_full is False
    assert sheet.authorized is False


# ---------------------------------------------------------------- Example C
def test_example_c_killed_by_d1_news_filter_despite_10_of_12_score():
    """Section 11.3: a 10/12, full-spine EU/USD NY KZ short is authorized
    by score alone, but the intended ~13:55 GMT entry sits inside the
    -60min blackout for a 14:30 GMT USD release (13:30-15:00 GMT). D1
    kills it outright — "No trade. Not at 10/12, not at 12/12."""
    # Narrative gives the headline total (10/12) without a full per-factor
    # breakdown ("drops only F8-adjacent nuance and one minor factor");
    # this reproduces that stated total with the spine full, which is all
    # the D1-filter behavior under test depends on.
    sheet = ScoreSheet(
        f1_htf_bias=2, f2_qualified_sweep=2, f3_m5_choch=2, f4_displacement_fvg=1,
        f5_poi_correct_zone=1, f6_inducement=1, f7_target_quality=1, f8_pool_seniority=0,
        f9_smt_divergence=0, f10_session_narrative=0,
        g1_time_and_disqualifiers=True, g2_stop_distance_band=True, g3_account_risk_limits=True,
    )
    assert sheet.total == 10
    assert sheet.authorized is True  # by score alone, before the filter is applied

    news_events = [
        NewsEvent(
            instrument_currencies=("USD",), event_time=datetime(2025, 1, 6, 14, 30, tzinfo=GMT),
            label="US Retail Sales + Fed speaker", is_red_folder=True,
        )
    ]
    intended_entry_time = datetime(2025, 1, 6, 13, 55, tzinfo=GMT)
    result = sessions_mod.check_d1_at_time(intended_entry_time, Instrument.EURUSD, news_events)
    assert result.blocked is True  # the filter overrides an authorized score — "no override in either direction"


def test_example_c_post_release_fresh_setup_is_not_blocked():
    """The blackout is time-scoped: a setup formed entirely after the
    release window (per D1's exception clause) is evaluated fresh."""
    news_events = [
        NewsEvent(
            instrument_currencies=("USD",), event_time=datetime(2025, 1, 6, 14, 30, tzinfo=GMT),
            label="US Retail Sales + Fed speaker", is_red_folder=True,
        )
    ]
    after_blackout = datetime(2025, 1, 6, 15, 5, tzinfo=GMT)
    result = sessions_mod.check_d1_at_time(after_blackout, Instrument.EURUSD, news_events)
    assert result.blocked is False
