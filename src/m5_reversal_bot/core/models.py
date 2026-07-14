"""Domain models for the M5 Liquidity Reversal Playbook.

These are pure data structures. No behavior that could bend a strategy rule
lives here — that logic lives exclusively in `strategy/*`, each module
citing the rulebook section/definition it implements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .enums import (
    CloseReason,
    Direction,
    EntryMethod,
    Instrument,
    Mode,
    PoolType,
    POISource,
    Session,
    SetupOutcome,
    TradeStatus,
)

TIMEFRAME_MINUTES = {"M5": 5, "H1": 60, "H4": 240}


@dataclass(frozen=True)
class Candle:
    """One M5/H1/H4 OHLC bar. Immutable — a closed candle never changes."""

    instrument: Instrument
    timeframe: str  # "M5" | "H1" | "H4"
    open_time: datetime  # GMT, bar open
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @property
    def body_high(self) -> float:
        return max(self.open, self.close)

    @property
    def body_low(self) -> float:
        return min(self.open, self.close)

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def range_size(self) -> float:
        return self.high - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def body_close_fraction(self) -> float:
        """Body size as a fraction of the candle's total range. Used by the
        rejection-close test (4.3) and the structure-quality filter (9.5)."""
        if self.range_size == 0:
            return 0.0
        return self.body_size / self.range_size

    @property
    def close_time(self) -> datetime:
        from datetime import timedelta

        return self.open_time + timedelta(minutes=TIMEFRAME_MINUTES[self.timeframe])


@dataclass(frozen=True)
class SwingPoint:
    """Definition 1.1 / 1.2 — confirmed 5-candle-fractal swing high/low."""

    instrument: Instrument
    timeframe: str
    kind: str  # "HIGH" | "LOW"
    price: float
    candle_time: datetime           # time of the extreme candle
    confirmed_time: datetime        # time the 2nd subsequent candle closed
    candle_index: int               # index into the working candle buffer


@dataclass(frozen=True)
class LiquidityPool:
    """Definition 1.5 — a qualified liquidity pool."""

    instrument: Instrument
    pool_type: PoolType
    price: float
    formed_time: datetime
    oldest_touch_time: datetime     # for F8 seniority (>=4h old)
    swept: bool = False


@dataclass(frozen=True)
class Sweep:
    """Definition 1.6 — a confirmed liquidity sweep (not a breakout)."""

    instrument: Instrument
    pool: LiquidityPool
    sweep_candle_time: datetime
    sweep_candle_index: int
    sweep_extreme_price: float      # the furthest traded price through the pool
    close_back_candle_time: datetime
    close_back_candle_index: int
    candles_to_close_back: int      # 0..3


@dataclass(frozen=True)
class FVG:
    """Definition 1.8 — Fair Value Gap."""

    instrument: Instrument
    direction: Direction
    candle1_time: datetime
    candle3_time: datetime
    gap_low: float
    gap_high: float

    @property
    def ce(self) -> float:
        """Consequent encroachment — the FVG midpoint."""
        return (self.gap_low + self.gap_high) / 2.0


@dataclass(frozen=True)
class OrderBlock:
    """Definition 1.9 — last opposite-direction candle before displacement."""

    instrument: Instrument
    direction: Direction            # direction of the trade this OB supports
    candle_time: datetime
    low: float
    high: float
    mitigated: bool = False

    @property
    def midpoint(self) -> float:
        return (self.low + self.high) / 2.0


@dataclass(frozen=True)
class CHoCH:
    """Definition 1.4 — confirmed Change of Character."""

    instrument: Instrument
    direction: Direction            # direction established BY the CHoCH
    confirm_candle_time: datetime
    confirm_candle_index: int
    close_price: float
    broken_swing: SwingPoint
    displacement_candle_time: Optional[datetime] = None
    displacement_confirmed: bool = False
    fvg: Optional[FVG] = None
    order_block: Optional[OrderBlock] = None


@dataclass(frozen=True)
class DealingRange:
    """Definition 1.11."""

    low: float   # sweep extreme (0%)
    high: float  # CHoCH confirmation candle close-side extreme (100%)

    @property
    def midpoint(self) -> float:
        return (self.low + self.high) / 2.0

    def in_discount(self, price: float) -> bool:
        return price <= self.midpoint

    def in_premium(self, price: float) -> bool:
        return price >= self.midpoint


@dataclass(frozen=True)
class POI:
    """Definition 1.10 — Point of Interest."""

    instrument: Instrument
    direction: Direction
    source: POISource
    zone_low: float
    zone_high: float
    entry_price: float              # CE of FVG, else OB 50%
    fvg: Optional[FVG] = None
    order_block: Optional[OrderBlock] = None

    def contains(self, price: float) -> bool:
        return self.zone_low <= price <= self.zone_high


@dataclass(frozen=True)
class Inducement:
    """Definition 1.12."""

    instrument: Instrument
    swing: SwingPoint


@dataclass
class ScoreSheet:
    """Section 3 — the 12-point scoring model plus the 3 mandatory gates."""

    f1_htf_bias: int = 0
    f2_qualified_sweep: int = 0
    f3_m5_choch: int = 0
    f4_displacement_fvg: int = 0
    f5_poi_correct_zone: int = 0
    f6_inducement: int = 0
    f7_target_quality: int = 0
    f8_pool_seniority: int = 0
    f9_smt_divergence: int = 0
    f10_session_narrative: int = 0

    g1_time_and_disqualifiers: bool = False
    g2_stop_distance_band: bool = False
    g3_account_risk_limits: bool = False

    reasons: dict = field(default_factory=dict)  # factor/gate -> explanation string

    @property
    def total(self) -> int:
        return (
            self.f1_htf_bias
            + self.f2_qualified_sweep
            + self.f3_m5_choch
            + self.f4_displacement_fvg
            + self.f5_poi_correct_zone
            + self.f6_inducement
            + self.f7_target_quality
            + self.f8_pool_seniority
            + self.f9_smt_divergence
            + self.f10_session_narrative
        )

    @property
    def spine_full(self) -> bool:
        return self.f1_htf_bias == 2 and self.f2_qualified_sweep == 2 and self.f3_m5_choch == 2

    @property
    def gates_pass(self) -> bool:
        return self.g1_time_and_disqualifiers and self.g2_stop_distance_band and self.g3_account_risk_limits

    @property
    def authorized(self) -> bool:
        """Section 3 decision rule, verbatim: score >= 9 AND spine full AND all gates pass."""
        return self.gates_pass and self.total >= 9 and self.spine_full

    def as_dict(self) -> dict:
        return {
            "F1_htf_bias": self.f1_htf_bias,
            "F2_qualified_sweep": self.f2_qualified_sweep,
            "F3_m5_choch": self.f3_m5_choch,
            "F4_displacement_fvg": self.f4_displacement_fvg,
            "F5_poi_correct_zone": self.f5_poi_correct_zone,
            "F6_inducement": self.f6_inducement,
            "F7_target_quality": self.f7_target_quality,
            "F8_pool_seniority": self.f8_pool_seniority,
            "F9_smt_divergence": self.f9_smt_divergence,
            "F10_session_narrative": self.f10_session_narrative,
            "total": self.total,
            "spine_full": self.spine_full,
            "G1": self.g1_time_and_disqualifiers,
            "G2": self.g2_stop_distance_band,
            "G3": self.g3_account_risk_limits,
            "gates_pass": self.gates_pass,
            "authorized": self.authorized,
            "reasons": dict(self.reasons),
        }


@dataclass
class Setup:
    """A scored (or filtered/voided) sweep-reversal candidate."""

    id: Optional[int]
    instrument: Instrument
    session: Session
    direction: Direction
    sweep: Sweep
    choch: CHoCH
    poi: Optional[POI]
    dealing_range: Optional[DealingRange]
    inducement: Optional[Inducement]
    score: ScoreSheet
    created_time: datetime
    outcome: SetupOutcome = SetupOutcome.SCORED_SKIP
    void_reason: Optional[str] = None


@dataclass
class RiskConstruction:
    """Section 5 stop, Section 6 targets, Section 8 sizing — computed together
    because F7 / G2 / sizing all depend on the same stop distance."""

    entry_price: float
    stop_price: float
    stop_distance: float
    buffer: float
    tp1_price: float
    tp1_r_multiple: float
    runner_target_price: Optional[float]
    position_size_lots: float
    risk_percent: float
    risk_amount: float


@dataclass
class Trade:
    """A live/paper/backtest trade instance, one per authorized setup (4.4)."""

    id: Optional[int]
    setup_id: Optional[int]
    mode: Mode
    instrument: Instrument
    session: Session
    direction: Direction
    entry_method: EntryMethod
    entry_price: float
    stop_price: float
    initial_stop_price: float
    buffer: float
    tp1_price: float
    runner_target_price: Optional[float]
    position_size_lots: float
    risk_percent: float
    status: TradeStatus = TradeStatus.PENDING
    order_id: Optional[str] = None
    submitted_time: Optional[datetime] = None
    filled_time: Optional[datetime] = None
    tp1_filled_time: Optional[datetime] = None
    be_applied: bool = False
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    close_reason: Optional[CloseReason] = None
    r_result: Optional[float] = None
    pnl: Optional[float] = None
    rule_compliance: bool = True
    deviations: list = field(default_factory=list)
    trail_events: list = field(default_factory=list)


@dataclass(frozen=True)
class NewsEvent:
    instrument_currencies: tuple  # e.g. ("USD", "EUR")
    event_time: datetime
    label: str
    is_red_folder: bool
    is_nfp_or_cpi: bool = False
    is_fomc: bool = False
    unscheduled: bool = False
