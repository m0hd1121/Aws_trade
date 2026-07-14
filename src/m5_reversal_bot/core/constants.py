"""Frozen strategy constants — THE M5 LIQUIDITY REVERSAL PLAYBOOK, v1.0.

WARNING TO FUTURE MAINTAINERS
==============================
Every value in this file is a direct transcription of a numbered rule in
`docs/strategy/M5_Liquidity_Reversal_Playbook.md`. This file must not be
edited to "optimize," "simplify," or "tune" the strategy. If the rulebook
document changes, the SHA-256 recorded in ``EXPECTED_RULEBOOK_SHA256``
below must be updated in the same commit, by the account holder, with a
commit message explaining the rule change — never silently.

`verify_strategy_integrity()` is called at process startup (see
`bot/runner.py`) and raises `StrategyIntegrityError` if the on-disk
rulebook no longer matches this hash, which means either the rulebook was
edited without updating this file, or this file drifted from the
rulebook. Either way the bot refuses to trade rather than run on rules
nobody signed off on.

The only values NOT frozen here are the two the rulebook itself calls out
as periodic, off-chart statistics recalibrated quarterly (D3/D4 Asia-range
band, and the XAU G2 band) — see `strategy/calibration.py`. Recalibration
changes thresholds within the method the rulebook defines; it never
changes the method itself.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from .enums import Instrument

REPO_ROOT = Path(__file__).resolve().parents[3]
RULEBOOK_PATH = REPO_ROOT / "docs" / "strategy" / "M5_Liquidity_Reversal_Playbook.md"

# Recorded at commit time via: sha256sum docs/strategy/M5_Liquidity_Reversal_Playbook.md
EXPECTED_RULEBOOK_SHA256 = "e0c1c1a0e2b1a387ad9ad1256c364648f926f443df63186e2f98420122f6d9e1"


class StrategyIntegrityError(RuntimeError):
    """Raised when the frozen rulebook file has been altered on disk."""


def verify_strategy_integrity(path: Path = RULEBOOK_PATH) -> None:
    if not path.exists():
        raise StrategyIntegrityError(
            f"Strategy rulebook not found at {path}. The bot will not start "
            "without the frozen source-of-truth document present."
        )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != EXPECTED_RULEBOOK_SHA256:
        raise StrategyIntegrityError(
            "Strategy rulebook hash mismatch. The frozen rulebook at "
            f"{path} does not match the hash recorded in core/constants.py "
            f"(expected {EXPECTED_RULEBOOK_SHA256}, got {digest}). "
            "The bot refuses to trade against an unverified rule set. "
            "If you intentionally changed the strategy, update "
            "EXPECTED_RULEBOOK_SHA256 yourself and record why in the commit "
            "message — this is the one file the bot will not change for you."
        )


@dataclass(frozen=True)
class InstrumentConstants:
    """Per-instrument numeric bands, all cited to their rulebook clause."""

    instrument: Instrument
    pip_value_in_price: float          # size of "1 pip"/"1 point" in price units

    # 1.5 equal highs/lows tolerance
    equal_level_tolerance: float
    equal_level_min_candle_gap: int = 8

    # 2.5 D3/D4 — Asia range disqualifiers (default calibration; see calibration.py)
    asia_range_min: float = 0.0
    asia_range_max: float = 0.0

    # 2.5 D7 — spread condition
    max_spread: float = 0.0

    # 5.2 buffer sizing bounds
    buffer_floor: float = 0.0
    buffer_cap: float = 0.0
    buffer_range_fraction: float = 0.15

    # 5.3 G2 — stop distance band (default calibration; see calibration.py)
    stop_distance_min: float = 0.0
    stop_distance_max: float = 0.0

    # 6.1 / 6.3 pool front-run offset
    pool_frontrun_offset: float = 0.0

    # 2.1 sweep-source confluence tolerance (Asia extreme <-> PDH/PDL)
    session_confluence_tolerance: float = 0.0


EU = InstrumentConstants(
    instrument=Instrument.EURUSD,
    pip_value_in_price=0.0001,
    equal_level_tolerance=0.00015,      # 1.5 pips
    asia_range_min=0.0015,              # 15 pips
    asia_range_max=0.0070,              # 70 pips
    max_spread=0.00012,                 # 1.2 pips
    buffer_floor=0.00015,               # 1.5 pips
    buffer_cap=0.00040,                 # 4.0 pips
    stop_distance_min=0.00050,          # 5.0 pips
    stop_distance_max=0.00150,          # 15.0 pips
    pool_frontrun_offset=0.0002,        # 2 pips
    session_confluence_tolerance=0.0010,  # 10 pips
)

XAU = InstrumentConstants(
    instrument=Instrument.XAUUSD,
    pip_value_in_price=0.01,            # $0.01 "point"; the rulebook works in $ directly
    equal_level_tolerance=0.50,         # $0.50
    asia_range_min=5.00,
    asia_range_max=28.00,
    max_spread=0.35,
    buffer_floor=0.40,
    buffer_cap=1.50,
    stop_distance_min=2.50,
    stop_distance_max=9.00,
    pool_frontrun_offset=0.60,
    session_confluence_tolerance=3.00,
)

INSTRUMENT_CONSTANTS = {
    Instrument.EURUSD: EU,
    Instrument.XAUUSD: XAU,
}


@dataclass(frozen=True)
class SessionWindows:
    """Section 2 — sessions & tradeable windows. All times GMT."""

    asia_start_hour: int = 0
    asia_end_hour: int = 6

    london_kz_start_hour: int = 7
    london_kz_end_hour: int = 10

    london_session_start_hour: int = 7   # 2.1 note: "London session high/low (07:00-12:00 GMT)"
    london_session_end_hour: int = 12

    newyork_kz_start_hour: int = 12
    newyork_kz_end_hour: int = 15

    order_validity_extension_minutes: int = 30   # 2.3
    hard_flat_hour: int = 19
    hard_flat_minute: int = 30                   # 2.4

    map_marking_hour: int = 6
    map_marking_minute: int = 45                 # Section 13 START


SESSIONS = SessionWindows()


@dataclass(frozen=True)
class StructureConstants:
    """1.1-1.4, 1.7 structure definitions."""

    swing_fractal_lookback: int = 2       # 2 candles before AND after
    swing_fractal_lookahead: int = 2
    displacement_body_lookback: int = 6   # 1.7 — larger than each of 6 preceding bodies
    choch_max_candles_from_sweep: int = 12  # F3 — within 12 M5 candles (60 min)
    sweep_max_close_back_candles: int = 3   # 1.6


STRUCTURE = StructureConstants()


@dataclass(frozen=True)
class ChopConstants:
    """1.14 chop condition."""

    lookback_candles_for_choch_count: int = 24
    min_bullish_chochs: int = 2
    min_bearish_chochs: int = 2
    lookback_candles_for_range: int = 12
    range_to_stop_multiple: float = 1.5


CHOP = ChopConstants()


@dataclass(frozen=True)
class ScoringConstants:
    """Section 3 — the scoring model.

    NOTE ON max_score: the rulebook states "12 points available," but its
    own per-factor weight table (F1-F3 at 2 pts, F4-F10 at 1 pt each) sums
    to 13, and Section 11.1's own worked example lists every one of the
    ten factors at full marks yet totals its "TOTAL" row as 12 — an
    arithmetic inconsistency in the source document itself, not something
    this codebase introduces. Per-factor weights are transcribed exactly
    as given (unchanged); max_score is set to the value those weights
    actually sum to, since no trading decision depends on the labeled
    maximum — only `min_score_to_trade` (>=9) and the spine requirement
    (F1=F2=F3=2) drive authorization, both transcribed verbatim and
    unaffected by this discrepancy.
    """

    min_score_to_trade: int = 9
    max_score: int = 13
    pool_seniority_min_age_hours: float = 4.0
    target_quality_min_r: float = 2.0

    # Point weights (F1-F10), cited for auditability against Section 3 table.
    weight_f1_htf_bias: int = 2
    weight_f2_qualified_sweep: int = 2
    weight_f3_m5_choch: int = 2
    weight_f4_displacement_fvg: int = 1
    weight_f5_poi_correct_zone: int = 1
    weight_f6_inducement: int = 1
    weight_f7_target_quality: int = 1
    weight_f8_pool_seniority: int = 1
    weight_f9_smt_divergence: int = 1
    weight_f10_session_narrative: int = 1


SCORING = ScoringConstants()


@dataclass(frozen=True)
class EntryConstants:
    """Section 4 — entry rules."""

    missed_move_fraction: float = 0.25       # 4.2 / 4.2c — 25% of POI->TP1 run
    rejection_close_min_body_fraction: float = 0.5  # 4.3


ENTRY = EntryConstants()


@dataclass(frozen=True)
class ExitConstants:
    """Section 6 — exits."""

    tp1_r_multiple: float = 2.0
    tp1_pool_window_max_r: float = 2.5
    tp1_partial_close_fraction: float = 0.5


EXITS = ExitConstants()


@dataclass(frozen=True)
class RiskConstants:
    """Section 8 — risk & money management."""

    normal_risk_percent: float = 1.0
    evaluation_risk_percent: float = 0.5
    evaluation_phase_trade_count: int = 40

    max_daily_loss_percent: float = 2.0
    max_weekly_loss_percent: float = 4.0
    consecutive_losses_session_limit: int = 2
    consecutive_losses_running_limit: int = 3
    max_trades_per_kill_zone: int = 2
    max_trades_per_day: int = 3
    max_concurrent_positions_total: int = 2
    max_concurrent_positions_per_instrument: int = 1
    max_combined_open_risk_percent_multi_instrument: float = 1.5

    monthly_drawdown_brake_percent: float = 6.0
    monthly_brake_requalify_trades: int = 20

    validation_demo_backtest_trades: int = 60
    validation_min_compliance_rate: float = 0.95
    validation_live_evaluation_trades: int = 40


RISK = RiskConstants()


@dataclass(frozen=True)
class NewsFilterConstants:
    """D1/D2 news blackout windows (minutes)."""

    blackout_minutes_before: int = 60
    blackout_minutes_after: int = 30
    blackout_kz_coverage_skip_fraction: float = 0.5
    nfp_cpi_release_hour_gmt: int = 12
    nfp_cpi_release_minute_gmt: int = 30
    nfp_cpi_nykz_resume_hour_gmt: int = 13
    nfp_cpi_nykz_resume_minute_gmt: int = 30


NEWS = NewsFilterConstants()


@dataclass(frozen=True)
class StructureQualityFilterConstants:
    """9.5 — sweep candle IS the CHoCH candle AND range > 60% of dealing range."""

    max_single_candle_dealing_range_fraction: float = 0.60


STRUCTURE_QUALITY = StructureQualityFilterConstants()


def get_instrument_constants(instrument: Instrument) -> InstrumentConstants:
    return INSTRUMENT_CONSTANTS[instrument]
