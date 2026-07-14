"""Section 13 — Decision Flowchart, realized as a mode-agnostic state
machine.

One `InstrumentEngine` runs per instrument. The identical engine drives
backtest, paper, demo, and live trading — only the execution adapter
underneath differs (`execution/*_adapter.py`). The engine never talks to a
broker directly; it only emits `EngineAction`s for `execution/order_manager.py`
to carry out. This is what guarantees "the same strategy logic is used
across backtesting, paper trading, demo trading, and live trading" — there
is exactly one code path that makes trading decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_type, datetime
from typing import Callable, List, Optional

from ..core.clock import (
    current_session,
    is_past_hard_flat,
    kill_zone_bounds,
    map_marking_time,
    order_validity_deadline,
    to_gmt,
)
from ..core.constants import RISK, SCORING, STRUCTURE, get_instrument_constants
from ..core.enums import (
    CloseReason,
    Direction,
    EntryMethod,
    Instrument,
    Mode,
    PoolType,
    POISource,
    Session,
    SetupOutcome,
    StrategyStage,
    TradeStatus,
)
from ..core.models import (
    Candle,
    CHoCH,
    LiquidityPool,
    NewsEvent,
    Setup,
    Sweep,
    Trade,
)
from . import checklist as checklist_mod
from . import chop as chop_mod
from . import displacement as displacement_mod
from . import entry as entry_mod
from . import exits as exits_mod
from . import filters as filters_mod
from . import inducement as inducement_mod
from . import liquidity as liquidity_mod
from . import order_block as order_block_mod
from . import poi as poi_mod
from . import risk as risk_mod
from . import scoring as scoring_mod
from . import sessions as sessions_mod
from . import smt as smt_mod
from . import stop_loss as stop_loss_mod
from . import structure as structure_mod
from . import trade_management as trade_management_mod


class EngineActionType:
    STAGE_CHANGED = "STAGE_CHANGED"
    DAY_LOCKED_OUT = "DAY_LOCKED_OUT"
    KZ_SKIPPED = "KZ_SKIPPED"
    SETUP_SCORED_SKIP = "SETUP_SCORED_SKIP"
    SETUP_VOIDED = "SETUP_VOIDED"
    SUBMIT_BRACKET_ORDER = "SUBMIT_BRACKET_ORDER"
    CANCEL_ORDER = "CANCEL_ORDER"
    APPLY_BREAKEVEN = "APPLY_BREAKEVEN"
    TRAIL_STOP = "TRAIL_STOP"
    CLOSE_ALL = "CLOSE_ALL"
    LOG_TRADE = "LOG_TRADE"


@dataclass
class EngineAction:
    type: str
    payload: dict = field(default_factory=dict)


@dataclass
class EngineDependencies:
    """Everything the engine needs from the outside world, injected so the
    strategy layer never imports execution/data/persistence code."""

    news_events_provider: Callable[[datetime], List[NewsEvent]]
    holiday_calendar: dict
    account_snapshot_provider: Callable[[], "risk_mod.AccountSnapshot"]
    reference_candles_provider: Callable[[], List[Candle]]
    current_spread_provider: Callable[[], float]
    bracket_order_supported: Callable[[], bool] = lambda: True


@dataclass
class _KZProgress:
    session: Session
    sweep: Optional[Sweep] = None
    choch: Optional[CHoCH] = None
    trades_taken: int = 0
    ended: bool = False


class InstrumentEngine:
    def __init__(self, instrument: Instrument, mode: Mode, deps: EngineDependencies):
        self.instrument = instrument
        self.mode = mode
        self.inst_constants = get_instrument_constants(instrument)
        self.deps = deps

        self.m5_candles: List[Candle] = []
        self.h1_candles: List[Candle] = []

        self.stage: StrategyStage = StrategyStage.STARTUP
        self.current_day: Optional[date_type] = None
        self.day_trading_allowed: bool = False
        self.day_block_reason: Optional[str] = None
        self.map_marked_today: bool = False
        self.pools: List[LiquidityPool] = []
        self.h1_bias: Optional[Direction] = None
        self.asia_high: Optional[float] = None
        self.asia_low: Optional[float] = None
        self.asia_range_value: Optional[float] = None

        self.recent_chochs: List[CHoCH] = []
        self.used_sweep_keys: set = set()

        self._kz: Optional[_KZProgress] = None
        self.pending_setup: Optional[Setup] = None
        self.pending_trade: Optional[Trade] = None
        self.active_trade: Optional[Trade] = None
        self._trail_since_index: int = 0

    # ------------------------------------------------------------------
    def _set_stage(self, stage: StrategyStage, detail: str = "") -> EngineAction:
        self.stage = stage
        return EngineAction(
            EngineActionType.STAGE_CHANGED,
            {"stage": stage.value, "detail": detail, "instrument": self.instrument.value},
        )

    def _sweep_key(self, sweep: Sweep):
        return (sweep.pool.pool_type, sweep.pool.price, sweep.sweep_candle_time)

    # ------------------------------------------------------------------ H1
    def process_h1_candle(self, candle: Candle) -> None:
        self.h1_candles.append(candle)

    # ------------------------------------------------------------------ M5 (main loop)
    def process_m5_candle(self, candle: Candle) -> List[EngineAction]:
        actions: List[EngineAction] = []
        self.m5_candles.append(candle)
        day = to_gmt(candle.open_time).date()

        if self.current_day != day:
            actions += self._start_new_day(day, candle.open_time)
            self.current_day = day

        if not self.day_trading_allowed:
            return actions

        if not self.map_marked_today and candle.open_time >= map_marking_time(candle.open_time):
            actions.append(self._set_stage(StrategyStage.MARKING_THE_MAP))
            self._mark_the_map(candle.open_time)
            self.map_marked_today = True

        if self.active_trade is not None and self.active_trade.status in (TradeStatus.OPEN, TradeStatus.PARTIAL):
            actions += self._manage_active_trade(candle)
            return actions

        if self.pending_trade is not None and self.pending_trade.status == TradeStatus.PENDING:
            actions += self._check_pending_order(candle)
            return actions

        if is_past_hard_flat(candle.close_time):
            actions.append(self._set_stage(StrategyStage.SESSION_ENDED, "past 19:30 GMT hard flat"))
            return actions

        session = current_session(candle.open_time)
        if session == Session.OUTSIDE_KZ:
            actions.append(self._set_stage(StrategyStage.WAITING_FOR_KILL_ZONE))
            self._kz = None
            return actions

        if self._kz is None or self._kz.session != session:
            self._kz = _KZProgress(session=session)

        if self._kz.ended:
            actions.append(self._set_stage(StrategyStage.SESSION_ENDED, f"{session.value} already ended"))
            return actions

        actions += self._run_kz_pipeline(candle, session)
        return actions

    # ------------------------------------------------------------------ daily map
    def _start_new_day(self, day: date_type, ref_time: datetime) -> List[EngineAction]:
        actions = [self._set_stage(StrategyStage.DAILY_LOCKOUT_CHECK)]
        snapshot = self.deps.account_snapshot_provider()

        d5 = sessions_mod.check_d5(ref_time, self.deps.holiday_calendar)
        if d5.blocked:
            self.day_trading_allowed = False
            self.day_block_reason = d5.reason
            actions.append(EngineAction(EngineActionType.DAY_LOCKED_OUT, {"reason": d5.reason}))
            return actions

        if snapshot.weekly_realized_loss_percent >= RISK.max_weekly_loss_percent:
            self.day_trading_allowed = False
            self.day_block_reason = "weekly loss limit reached"
            actions.append(EngineAction(EngineActionType.DAY_LOCKED_OUT, {"reason": self.day_block_reason}))
            return actions

        if snapshot.monthly_brake_active:
            self.day_trading_allowed = False
            self.day_block_reason = "monthly drawdown brake active"
            actions.append(EngineAction(EngineActionType.DAY_LOCKED_OUT, {"reason": self.day_block_reason}))
            return actions

        self.day_trading_allowed = True
        self.day_block_reason = None
        self.map_marked_today = False  # actual marking happens at/after 06:45 GMT — see process_m5_candle
        return actions

    def _mark_the_map(self, ref_time: datetime) -> None:
        swing_highs, swing_lows = structure_mod.find_all_swings(self.m5_candles)
        self.pools = liquidity_mod.build_all_pools(
            self.m5_candles, swing_highs, swing_lows, self.instrument, self.inst_constants, ref_time
        )
        asia = liquidity_mod.compute_asia_range(self.m5_candles, ref_time)
        if asia:
            self.asia_high, self.asia_low, self.asia_range_value = asia
        self.h1_bias = scoring_mod.compute_h1_bias(self.h1_candles) if self.h1_candles else None
        self.recent_chochs = []
        self.used_sweep_keys = set()

    def _asia_band_ok(self) -> bool:
        if self.asia_range_value is None:
            return False
        return not sessions_mod.check_d3_d4(self.instrument, self.asia_range_value, self.inst_constants).blocked

    # ------------------------------------------------------------------ KZ pipeline
    def _kz_start_index(self, session: Session, ref_time: datetime) -> int:
        kz_start, _ = kill_zone_bounds(session, ref_time)
        for i, c in enumerate(self.m5_candles):
            if c.open_time >= kz_start:
                return i
        return max(0, len(self.m5_candles) - 1)

    def _relevant_pool_types(self, session: Session) -> set:
        if session == Session.LONDON_KZ:
            return {PoolType.ASIA_HIGH, PoolType.ASIA_LOW, PoolType.PDH, PoolType.PDL}
        return {
            PoolType.LONDON_HIGH, PoolType.LONDON_LOW,
            PoolType.LKZ_HIGH, PoolType.LKZ_LOW,
            PoolType.PDH, PoolType.PDL,
        }

    def _find_fresh_sweep(self, session: Session, candle: Candle) -> Optional[Sweep]:
        start_idx = self._kz_start_index(session, candle.open_time)
        relevant_types = self._relevant_pool_types(session) | {PoolType.EQUAL_HIGHS, PoolType.EQUAL_LOWS}
        best: Optional[Sweep] = None
        for pool in self.pools:
            if pool.pool_type not in relevant_types:
                continue
            if session == Session.LONDON_KZ and pool.pool_type in (PoolType.PDH, PoolType.PDL):
                asia_extreme = self.asia_high if pool.pool_type == PoolType.PDH else self.asia_low
                if not sessions_mod.check_session_confluence(session, pool.price, asia_extreme, self.inst_constants):
                    continue
            sweep = liquidity_mod.detect_sweep(self.m5_candles, pool, start_idx)
            if sweep is None:
                continue
            if self._sweep_key(sweep) in self.used_sweep_keys:
                continue
            if best is None or sweep.sweep_candle_index < best.sweep_candle_index:
                best = sweep
        return best

    def _find_choch_after_sweep(self, sweep: Sweep) -> Optional[CHoCH]:
        direction = Direction.LONG if sweep.pool.pool_type in liquidity_mod.LOW_POOL_TYPES else Direction.SHORT
        swing_highs, swing_lows = structure_mod.find_all_swings(self.m5_candles)
        opposite = swing_highs if direction == Direction.LONG else swing_lows
        return structure_mod.detect_choch(self.m5_candles, sweep.close_back_candle_index, direction, opposite)

    def _run_kz_pipeline(self, candle: Candle, session: Session) -> List[EngineAction]:
        actions: List[EngineAction] = []

        if session == Session.LONDON_KZ and self.asia_range_value is not None:
            d3d4 = sessions_mod.check_d3_d4(self.instrument, self.asia_range_value, self.inst_constants)
            if d3d4.blocked:
                self._kz.ended = True
                actions.append(EngineAction(EngineActionType.KZ_SKIPPED, {"reason": d3d4.reason}))
                actions.append(self._set_stage(StrategyStage.SESSION_ENDED, d3d4.reason))
                return actions

        actions.append(self._set_stage(StrategyStage.SESSION_DISQUALIFIER_CHECK))
        news_events = self.deps.news_events_provider(candle.open_time)
        for check in (
            sessions_mod.check_d1_session(session, candle.open_time, self.instrument, news_events),
            sessions_mod.check_d2(session, candle.open_time, candle.open_time, self.instrument, news_events),
            sessions_mod.check_d6(candle.open_time),
        ):
            if check.blocked:
                self._kz.ended = True
                actions.append(EngineAction(EngineActionType.KZ_SKIPPED, {"reason": check.reason}))
                actions.append(self._set_stage(StrategyStage.SESSION_ENDED, check.reason))
                return actions

        spread = self.deps.current_spread_provider()
        d7 = sessions_mod.check_d7(self.instrument, spread, self.inst_constants)
        if d7.blocked:
            actions.append(self._set_stage(StrategyStage.SESSION_DISQUALIFIER_CHECK, d7.reason))
            return actions  # transient — wait for spread to normalize, KZ stays open

        actions.append(self._set_stage(StrategyStage.ACCOUNT_STATE_CHECK))
        snapshot = self.deps.account_snapshot_provider()
        risk_pct = risk_mod.determine_risk_percent(snapshot)
        g3 = risk_mod.evaluate_g3(snapshot, self.instrument, risk_pct)
        if not g3.g3_pass:
            self._kz.ended = True
            actions.append(EngineAction(EngineActionType.KZ_SKIPPED, {"reason": "; ".join(g3.blocked_reasons)}))
            actions.append(self._set_stage(StrategyStage.SESSION_ENDED, "account-state filter tripped"))
            return actions

        if self._kz.sweep is None:
            actions.append(self._set_stage(StrategyStage.WAITING_FOR_SWEEP))
            sweep = self._find_fresh_sweep(session, candle)
            if sweep is None:
                kz_start, kz_end = kill_zone_bounds(session, candle.open_time)
                if candle.close_time >= kz_end:
                    self._kz.ended = True
                    actions.append(self._set_stage(StrategyStage.SESSION_ENDED, "KZ ended with no sweep"))
                return actions
            self._kz.sweep = sweep

        if self._kz.choch is None:
            actions.append(self._set_stage(StrategyStage.WAITING_FOR_CHOCH))
            choch = self._find_choch_after_sweep(self._kz.sweep)
            if choch is None:
                candles_since = len(self.m5_candles) - 1 - self._kz.sweep.sweep_candle_index
                if candles_since > STRUCTURE.choch_max_candles_from_sweep:
                    self.used_sweep_keys.add(self._sweep_key(self._kz.sweep))
                    self._kz.sweep = None
                return actions
            self._kz.choch = choch
            self.recent_chochs.append(choch)

        actions += self._evaluate_setup(candle, session, self._kz.sweep, self._kz.choch)
        return actions

    def _void_setup(self, actions: List[EngineAction], sweep: Sweep, reason: str) -> None:
        actions.append(EngineAction(EngineActionType.SETUP_VOIDED, {"reason": reason, "instrument": self.instrument.value}))
        self.used_sweep_keys.add(self._sweep_key(sweep))
        self._kz.sweep = None
        self._kz.choch = None

    # ------------------------------------------------------------------ scoring + construction
    def _evaluate_setup(self, candle: Candle, session: Session, sweep: Sweep, choch: CHoCH) -> List[EngineAction]:
        actions: List[EngineAction] = []
        direction = choch.direction

        leg_start, leg_end = sweep.sweep_candle_index, choch.confirm_candle_index
        disp = displacement_mod.detect_displacement(self.m5_candles, leg_start, leg_end, direction)
        displacement_index, fvg = disp if disp else (None, None)
        ob_source_index = displacement_index if displacement_index is not None else choch.confirm_candle_index
        ob = order_block_mod.find_order_block(self.m5_candles, ob_source_index, direction) if ob_source_index > 0 else None

        dealing_range = poi_mod.build_dealing_range(sweep, choch)
        poi = poi_mod.build_poi(fvg, ob, dealing_range, direction)

        sweep_candle = self.m5_candles[sweep.sweep_candle_index]
        spread = self.deps.current_spread_provider()
        buffer = stop_loss_mod.compute_buffer(spread, sweep_candle, self.inst_constants)
        stop_price = stop_loss_mod.compute_stop_price(direction, sweep.sweep_extreme_price, buffer)
        entry_price = poi.entry_price if poi else candle.close
        distance = stop_loss_mod.stop_distance(entry_price, stop_price)

        actions.append(self._set_stage(StrategyStage.CHOP_CHECK))
        if chop_mod.is_chop(self.m5_candles, len(self.m5_candles) - 1, self.recent_chochs, distance):
            self._void_setup(actions, sweep, "chop condition met (1.14)")
            return actions

        actions.append(self._set_stage(StrategyStage.NEWS_BLACKOUT_CHECK))
        news_events = self.deps.news_events_provider(candle.open_time)
        order_deadline = order_validity_deadline(session, candle.open_time)
        d1_at_rest = sessions_mod.check_d1_at_time(candle.close_time, self.instrument, news_events)
        d1_at_deadline = sessions_mod.check_d1_at_time(order_deadline, self.instrument, news_events)
        if d1_at_rest.blocked or d1_at_deadline.blocked:
            self._void_setup(actions, sweep, (d1_at_rest.reason or d1_at_deadline.reason))
            return actions

        actions.append(self._set_stage(StrategyStage.SCORING_SETUP))

        # Mitigation must be checked starting AFTER the displacement leg
        # that created the POI fully completes — not from the leg's own
        # candles. The FVG's defining triple is (displacement_index-1,
        # displacement_index, displacement_index+1); checking from
        # anywhere inside that triple (e.g. choch.confirm_candle_index,
        # which often IS the displacement candle) reads the impulsive
        # move's own range as "already retraded," falsely mitigating a
        # POI on the very candle that formed it.
        fvg_check_start = displacement_index + 2 if displacement_index is not None else choch.confirm_candle_index + 1
        ob_check_start = displacement_index + 1 if displacement_index is not None else choch.confirm_candle_index + 1

        # Mitigation is checked against whichever structure actually
        # defines THIS poi's zone (poi.source) — not "FVG first, then OB"
        # regardless of which one the entry is built on. `poi.fvg` /
        # `poi.order_block` may both be populated for reference even when
        # only one of them defines the scored zone (see poi.py's Example-A
        # fallback), so checking the wrong one would score a live,
        # untouched POI as mitigated just because the OTHER structure from
        # the same leg got retraded.
        mitigated = False
        if poi and poi.source == POISource.ORDER_BLOCK and poi.order_block:
            mitigated = order_block_mod.is_order_block_mitigated(self.m5_candles, poi.order_block, ob_check_start)
        elif poi and poi.fvg:
            mitigated = poi_mod.is_fvg_mitigated(self.m5_candles, poi.fvg, fvg_check_start)

        smt_present = False
        ref_candles = self.deps.reference_candles_provider()
        if ref_candles:
            ref_highs, ref_lows = structure_mod.find_all_swings(ref_candles)
            ref_pools = liquidity_mod.build_all_pools(
                ref_candles, ref_highs, ref_lows, self.instrument, self.inst_constants, candle.open_time
            )
            ref_level = smt_mod.find_reference_equivalent_level(ref_pools, sweep.pool.pool_type)
            if ref_level is not None:
                smt_present = smt_mod.check_smt_divergence(sweep, ref_candles, ref_level)

        swing_highs, swing_lows = structure_mod.find_all_swings(self.m5_candles)
        inducement = inducement_mod.find_inducement(choch, poi, direction, swing_lows, swing_highs) if poi else None

        score = scoring_mod.build_score_sheet(
            h1_bias=self.h1_bias, direction=direction, sweep=sweep, choch=choch,
            displacement_found=disp is not None, poi=poi, dealing_range=dealing_range,
            poi_mitigated=mitigated, inducement=inducement, entry_price=entry_price,
            stop_distance=distance, all_pools=self.pools, smt_present=smt_present,
            session=session, ref_date=candle.open_time,
        )

        g2_pass = stop_loss_mod.check_g2_stop_band(distance, self.inst_constants)
        score.g2_stop_distance_band = g2_pass

        snapshot = self.deps.account_snapshot_provider()
        risk_pct = risk_mod.determine_risk_percent(snapshot)
        g3 = risk_mod.evaluate_g3(snapshot, self.instrument, risk_pct)
        score.g3_account_risk_limits = g3.g3_pass

        d1_session = sessions_mod.check_d1_session(session, candle.open_time, self.instrument, news_events)
        score.g1_time_and_disqualifiers = not d1_session.blocked

        setup = Setup(
            id=None, instrument=self.instrument, session=session, direction=direction,
            sweep=sweep, choch=choch, poi=poi, dealing_range=dealing_range,
            inducement=inducement, score=score, created_time=candle.open_time,
        )

        if filters_mod.is_structure_quality_filtered(sweep, choch, dealing_range, sweep_candle):
            self._void_setup(actions, sweep, "structure-quality filter (9.5)")
            return actions

        if not score.authorized:
            # F6 (inducement) requires a confirmed swing formed AFTER the
            # CHoCH (1.12) — which structurally cannot exist on the CHoCH
            # candle itself. Section 11.1's own worked example shows the
            # inducement swing forming a candle after CHoCH confirmation
            # and still being scored into the same authorization. So a
            # score that only misses because the post-CHoCH picture (POI
            # mitigation, inducement) hasn't fully formed YET is retried
            # on the next candle rather than discarded outright — bounded
            # by the same window F3 already uses for "how long we wait on
            # this sweep" (STRUCTURE.choch_max_candles_from_sweep), so a
            # setup can't be re-scored forever.
            candles_since_sweep = len(self.m5_candles) - 1 - sweep.sweep_candle_index
            window_open = candles_since_sweep <= STRUCTURE.choch_max_candles_from_sweep
            if window_open:
                actions.append(self._set_stage(StrategyStage.SCORING_SETUP, "score below bar — waiting for post-CHoCH factors (inducement/POI) to firm up"))
                return actions
            setup.outcome = SetupOutcome.SCORED_SKIP
            actions.append(EngineAction(EngineActionType.SETUP_SCORED_SKIP, {"setup": setup, "score": score.as_dict()}))
            self.used_sweep_keys.add(self._sweep_key(sweep))
            self._kz.sweep = None
            self._kz.choch = None
            return actions

        actions.append(self._set_stage(StrategyStage.CONSTRUCTING_TRADE))

        tp1_price, tp1_r, tp1_pool = exits_mod.compute_tp1(entry_price, distance, direction, self.pools, self.inst_constants)
        runner_target = exits_mod.compute_runner_target(entry_price, tp1_price, direction, self.pools, self.inst_constants, tp1_pool=tp1_pool)
        position_size = risk_mod.compute_position_size(snapshot.equity_start_of_day, risk_pct, distance, self.instrument)

        if entry_mod.is_missed_move(candle.close, entry_price, tp1_price, direction, baseline_price=choch.close_price):
            self._void_setup(actions, sweep, "missed-move filter — price ran >=25% of POI->TP1 before order existed")
            return actions

        checklist_flags = [
            True,                                    # 1  time inside LKZ/NYKZ (guaranteed by pipeline)
            not d1_session.blocked,                   # 2  no session disqualifier D1-D7 active
            self._asia_band_ok(),                     # 3  Asia range inside D3/D4 band
            not d1_at_rest.blocked,                    # 4  no red news within -60/+30 min
            True,                                      # 5  chop NOT met (already verified above)
            score.f1_htf_bias == 2,                    # 6  H1 bias supports direction
            score.f2_qualified_sweep == 2,              # 7  qualified pool swept
            score.f3_m5_choch == 2,                     # 8  M5 CHoCH confirmed within window
            score.total >= SCORING.min_score_to_trade,  # 9  total score >= 9/12
            score.f5_poi_correct_zone == 1,             # 10 POI unmitigated, correct zone
            g2_pass,                                    # 11 stop distance inside G2 band
            score.f7_target_quality == 1,                # 12 TP1 >= 2.0R
            position_size > 0,                           # 13 position size computed, rounded down
            g3.g3_pass,                                   # 14 daily/weekly/loss/trade-count limits clear
            self.deps.bracket_order_supported(),           # 15 bracket ready to submit as one unit
        ]
        rows = checklist_mod.build_checklist(checklist_flags)

        if not checklist_mod.checklist_passed(rows):
            self._void_setup(actions, sweep, "checklist failed after construction — see checklist rows")
            return actions

        setup.outcome = SetupOutcome.TAKEN
        trade = Trade(
            id=None, setup_id=None, mode=self.mode, instrument=self.instrument, session=session,
            direction=direction, entry_method=EntryMethod.RESTING_LIMIT, entry_price=entry_price,
            stop_price=stop_price, initial_stop_price=stop_price, buffer=buffer, tp1_price=tp1_price,
            runner_target_price=runner_target, position_size_lots=position_size, risk_percent=risk_pct,
            status=TradeStatus.PENDING,
        )
        self.pending_trade = trade
        self.pending_setup = setup

        actions.append(self._set_stage(StrategyStage.SUBMITTING_BRACKET_ORDER))
        actions.append(EngineAction(EngineActionType.SUBMIT_BRACKET_ORDER, {
            "trade": trade, "setup": setup, "checklist": rows,
            "order_valid_until": order_validity_deadline(session, candle.open_time),
        }))
        actions.append(self._set_stage(StrategyStage.WAITING_FOR_FILL))
        return actions

    # ------------------------------------------------------------------ pending order lifecycle (4.2)
    def _check_pending_order(self, candle: Candle) -> List[EngineAction]:
        actions: List[EngineAction] = []
        trade, setup = self.pending_trade, self.pending_setup

        if entry_mod.is_poi_violated(candle, setup.poi, trade.direction):
            actions.append(self._cancel_pending(trade, setup, "POI violated before fill (4.2)"))
            return actions

        swing_highs, swing_lows = structure_mod.find_all_swings(self.m5_candles)
        opposing_direction = Direction.SHORT if trade.direction == Direction.LONG else Direction.LONG
        # A SHORT-direction CHoCH search needs swing LOWS as its reference
        # (per detect_choch's contract); a LONG-direction search needs
        # swing HIGHS. Since `opposing_direction` is the mirror of the
        # trade's own direction, the swing set is the mirror of the set
        # `_find_choch_after_sweep` would use for the trade's own direction.
        swings_for_opposing_search = swing_lows if opposing_direction == Direction.SHORT else swing_highs
        opposing_choch = structure_mod.detect_choch(
            self.m5_candles, setup.choch.confirm_candle_index + 1, opposing_direction, swings_for_opposing_search
        )
        if opposing_choch is not None:
            actions.append(self._cancel_pending(trade, setup, "opposing M5 CHoCH printed (4.2)"))
            return actions

        if entry_mod.is_missed_move(candle.close, trade.entry_price, trade.tp1_price, trade.direction, baseline_price=setup.choch.close_price):
            actions.append(self._cancel_pending(trade, setup, "price ran >=25% of POI->TP1 without fill (4.2)"))
            return actions

        order_deadline = order_validity_deadline(setup.session, candle.open_time)
        if candle.close_time >= order_deadline:
            actions.append(self._cancel_pending(trade, setup, "KZ close + 30 min — order validity expired (2.3)"))
            return actions

        news_events = self.deps.news_events_provider(candle.open_time)
        if sessions_mod.event_in_blackout_at(candle.close_time, self.instrument, news_events):
            actions.append(self._cancel_pending(trade, setup, "news blackout began (D1) — cancel per 4.2"))
            return actions

        actions.append(self._set_stage(StrategyStage.WAITING_FOR_FILL))
        return actions

    def _cancel_pending(self, trade: Trade, setup: Setup, reason: str) -> EngineAction:
        trade.status = TradeStatus.CANCELLED
        self.used_sweep_keys.add(self._sweep_key(setup.sweep))
        self.pending_trade = None
        self.pending_setup = None
        if self._kz:
            self._kz.sweep = None
            self._kz.choch = None
        return EngineAction(EngineActionType.CANCEL_ORDER, {"trade": trade, "reason": reason})

    def check_intrabar_pending_conditions(self, current_price: float, current_time: datetime) -> List[EngineAction]:
        """Lets execution adapters react intrabar (tick-level) to the 25%
        missed-move rule and a news blackout beginning, rather than waiting
        for the next M5 close (4.2)."""
        actions: List[EngineAction] = []
        if self.pending_trade is None or self.pending_setup is None:
            return actions
        trade, setup = self.pending_trade, self.pending_setup
        if entry_mod.is_missed_move(current_price, trade.entry_price, trade.tp1_price, trade.direction, baseline_price=setup.choch.close_price):
            actions.append(self._cancel_pending(trade, setup, "price ran >=25% of POI->TP1 without fill (4.2, intrabar)"))
            return actions
        news_events = self.deps.news_events_provider(current_time)
        if sessions_mod.event_in_blackout_at(current_time, self.instrument, news_events):
            actions.append(self._cancel_pending(trade, setup, "news blackout began (D1, intrabar) — cancel per 4.2"))
        return actions

    def check_unscheduled_news_flatten(self, current_time: datetime) -> List[EngineAction]:
        """7.3 — the single manual-exit exception."""
        actions: List[EngineAction] = []
        if self.active_trade is None:
            return actions
        news_events = self.deps.news_events_provider(current_time)
        unscheduled = [e for e in news_events if e.unscheduled and e.is_red_folder]
        event = trade_management_mod.unscheduled_news_flatten_required(self.active_trade, unscheduled)
        if event:
            actions.append(EngineAction(EngineActionType.CLOSE_ALL, {
                "trade": self.active_trade, "reason": CloseReason.UNSCHEDULED_NEWS_FLATTEN, "event": event.label,
            }))
            self._clear_active_trade_state()
        return actions

    def _clear_active_trade_state(self) -> None:
        """Mirrors the bookkeeping `on_trade_closed` does, for the CLOSE_ALL
        paths (hard flat, emergency stop, unscheduled news) that bypass the
        normal fill-reported close — otherwise `active_trade` would dangle
        in a CLOSED status and the engine would never resume waiting for a
        fresh sweep (4.4)."""
        self.active_trade = None
        if self._kz:
            self._kz.sweep = None
            self._kz.choch = None
            self._kz.trades_taken += 1

    # ------------------------------------------------------------------ post-fill management (Section 7)
    def on_order_filled(self, fill_price: float, fill_time: datetime) -> List[EngineAction]:
        actions: List[EngineAction] = []
        if self.pending_trade is None:
            return actions
        trade = self.pending_trade
        trade.status = TradeStatus.OPEN
        trade.filled_time = fill_time
        self.active_trade = trade
        self.pending_trade = None
        self.pending_setup = None
        self._trail_since_index = len(self.m5_candles)
        actions.append(self._set_stage(StrategyStage.MONITORING_PRE_TP1))
        return actions

    def on_tp1_filled(self, fill_time: datetime, spread: float) -> List[EngineAction]:
        actions: List[EngineAction] = []
        trade = self.active_trade
        if trade is None:
            return actions
        trade.status = TradeStatus.PARTIAL
        trade.tp1_filled_time = fill_time
        be_price = exits_mod.breakeven_stop(trade.direction, trade.entry_price, spread)
        if not stop_loss_mod.is_stop_widening(trade.direction, trade.stop_price, be_price):
            trade.stop_price = be_price
            trade.be_applied = True
            actions.append(EngineAction(EngineActionType.APPLY_BREAKEVEN, {"trade": trade, "new_stop": be_price}))
        self._trail_since_index = len(self.m5_candles)
        actions.append(self._set_stage(StrategyStage.TRAILING_RUNNER))
        return actions

    def _manage_active_trade(self, candle: Candle) -> List[EngineAction]:
        actions: List[EngineAction] = []
        trade = self.active_trade

        if is_past_hard_flat(candle.close_time):
            actions.append(self._set_stage(StrategyStage.HARD_FLAT_CLOSE))
            actions.append(EngineAction(EngineActionType.CLOSE_ALL, {"trade": trade, "reason": CloseReason.HARD_FLAT}))
            self._clear_active_trade_state()
            return actions

        if trade.status == TradeStatus.OPEN:
            actions.append(self._set_stage(StrategyStage.MONITORING_PRE_TP1))
            return actions

        if trade.status == TradeStatus.PARTIAL:
            actions.append(self._set_stage(StrategyStage.TRAILING_RUNNER))
            swing_highs, swing_lows = structure_mod.find_all_swings(self.m5_candles)
            swings_for_bos = swing_highs if trade.direction == Direction.LONG else swing_lows
            protective_swings = swing_lows if trade.direction == Direction.LONG else swing_highs
            events = structure_mod.detect_bos_events_since(
                self.m5_candles, self._trail_since_index, trade.direction, swings_for_bos
            )
            for idx, _broken in events:
                protective = structure_mod.most_recent_confirmed_opposite_swing(
                    self.m5_candles, idx, trade.direction, protective_swings
                )
                if protective is None:
                    continue
                new_stop = exits_mod.trail_stop_from_swing(trade.direction, protective.price, trade.buffer)
                if not stop_loss_mod.is_stop_widening(trade.direction, trade.stop_price, new_stop):
                    trade.stop_price = new_stop
                    trade.trail_events.append({"time": candle.open_time.isoformat(), "new_stop": new_stop})
                    actions.append(EngineAction(EngineActionType.TRAIL_STOP, {"trade": trade, "new_stop": new_stop}))
            self._trail_since_index = len(self.m5_candles)
        return actions

    def on_trade_closed(self, exit_price: float, exit_time: datetime, reason: CloseReason) -> List[EngineAction]:
        actions: List[EngineAction] = []
        trade = self.active_trade
        if trade is None:
            return actions
        trade.status = TradeStatus.CLOSED
        trade.exit_price = exit_price
        trade.exit_time = exit_time
        trade.close_reason = reason
        self.active_trade = None
        if self._kz:
            self._kz.sweep = None
            self._kz.choch = None
            self._kz.trades_taken += 1
        actions.append(self._set_stage(StrategyStage.LOGGING_TRADE))
        actions.append(EngineAction(EngineActionType.LOG_TRADE, {"trade": trade}))
        return actions

    # ------------------------------------------------------------------ bot controls
    def emergency_stop(self) -> List[EngineAction]:
        actions = [self._set_stage(StrategyStage.EMERGENCY_STOPPED, "manual emergency stop")]
        if self.active_trade:
            actions.append(EngineAction(EngineActionType.CLOSE_ALL, {"trade": self.active_trade, "reason": CloseReason.EMERGENCY_STOP}))
            self._clear_active_trade_state()
        if self.pending_trade:
            actions.append(EngineAction(EngineActionType.CANCEL_ORDER, {"trade": self.pending_trade, "reason": "emergency stop"}))
            self.pending_trade = None
            self.pending_setup = None
        self.day_trading_allowed = False
        return actions

    def reset_session(self) -> None:
        """Reset Session control — clears in-memory KZ/day progress. Never
        touches persisted trade history; that ledger is permanent."""
        self._kz = None
        self.current_day = None
        self.day_trading_allowed = False
        self.pending_trade = None
        self.pending_setup = None
