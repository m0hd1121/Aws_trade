"""Enumerations shared across the strategy, execution, and persistence layers."""

from enum import Enum


class Instrument(str, Enum):
    EURUSD = "EURUSD"
    XAUUSD = "XAUUSD"


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class Session(str, Enum):
    LONDON_KZ = "LONDON_KZ"
    NEWYORK_KZ = "NEWYORK_KZ"
    OUTSIDE_KZ = "OUTSIDE_KZ"


class PoolType(str, Enum):
    """Definition 1.5 — qualified liquidity pools."""

    ASIA_HIGH = "ASIA_HIGH"
    ASIA_LOW = "ASIA_LOW"
    PDH = "PDH"
    PDL = "PDL"
    PWH = "PWH"
    PWL = "PWL"
    LONDON_HIGH = "LONDON_HIGH"     # full London session 07:00-12:00 GMT
    LONDON_LOW = "LONDON_LOW"
    LKZ_HIGH = "LKZ_HIGH"           # London Kill Zone extreme, 07:00-10:00 GMT
    LKZ_LOW = "LKZ_LOW"
    EQUAL_HIGHS = "EQUAL_HIGHS"
    EQUAL_LOWS = "EQUAL_LOWS"


class POISource(str, Enum):
    FVG = "FVG"
    ORDER_BLOCK = "ORDER_BLOCK"
    FVG_OB_OVERLAP = "FVG_OB_OVERLAP"


class EntryMethod(str, Enum):
    RESTING_LIMIT = "RESTING_LIMIT"
    CONFIRMATION_MARKET = "CONFIRMATION_MARKET"


class SetupOutcome(str, Enum):
    """What ultimately happened to a scored setup."""

    AUTHORIZED_PENDING = "AUTHORIZED_PENDING"
    TAKEN = "TAKEN"
    SCORED_SKIP = "SCORED_SKIP"      # scored, failed score/spine
    VOIDED = "VOIDED"                # authorized then invalidated pre-fill
    FILTERED = "FILTERED"            # killed by an absolute filter / gate / disqualifier


class TradeStatus(str, Enum):
    PENDING = "PENDING"
    CANCELLED = "CANCELLED"
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"       # TP1 filled, runner open
    CLOSED = "CLOSED"


class CloseReason(str, Enum):
    STOP_LOSS = "STOP_LOSS"
    TP1 = "TP1"
    RUNNER_TARGET = "RUNNER_TARGET"
    TRAILED_OUT = "TRAILED_OUT"
    HARD_FLAT = "HARD_FLAT"
    UNSCHEDULED_NEWS_FLATTEN = "UNSCHEDULED_NEWS_FLATTEN"
    EMERGENCY_STOP = "EMERGENCY_STOP"


class Mode(str, Enum):
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    DEMO = "DEMO"
    LIVE = "LIVE"


class BotState(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    EMERGENCY_STOPPED = "EMERGENCY_STOPPED"
    RESTARTING = "RESTARTING"


class StrategyStage(str, Enum):
    """Drives the dashboard's step-by-step execution transparency panel.

    Every value maps 1:1 to a step in Section 13's decision flowchart so the
    dashboard can always show *which rule* the bot is currently evaluating.
    """

    STARTUP = "STARTUP"
    DAILY_LOCKOUT_CHECK = "DAILY_LOCKOUT_CHECK"           # holiday / weekly-loss / monthly-brake
    MARKING_THE_MAP = "MARKING_THE_MAP"                    # 06:45 GMT map marking
    WAITING_FOR_KILL_ZONE = "WAITING_FOR_KILL_ZONE"
    SESSION_DISQUALIFIER_CHECK = "SESSION_DISQUALIFIER_CHECK"  # D1-D7
    ACCOUNT_STATE_CHECK = "ACCOUNT_STATE_CHECK"             # section 8 breakers
    WAITING_FOR_SWEEP = "WAITING_FOR_SWEEP"
    WAITING_FOR_CHOCH = "WAITING_FOR_CHOCH"
    CHOP_CHECK = "CHOP_CHECK"
    NEWS_BLACKOUT_CHECK = "NEWS_BLACKOUT_CHECK"
    SCORING_SETUP = "SCORING_SETUP"
    CONSTRUCTING_TRADE = "CONSTRUCTING_TRADE"               # POI/stop/G2/F7/sizing
    SUBMITTING_BRACKET_ORDER = "SUBMITTING_BRACKET_ORDER"
    WAITING_FOR_FILL = "WAITING_FOR_FILL"
    MONITORING_PRE_TP1 = "MONITORING_PRE_TP1"
    MANAGING_POST_TP1 = "MANAGING_POST_TP1"
    TRAILING_RUNNER = "TRAILING_RUNNER"
    HARD_FLAT_CLOSE = "HARD_FLAT_CLOSE"
    LOGGING_TRADE = "LOGGING_TRADE"
    SESSION_ENDED = "SESSION_ENDED"
    EMERGENCY_STOPPED = "EMERGENCY_STOPPED"
