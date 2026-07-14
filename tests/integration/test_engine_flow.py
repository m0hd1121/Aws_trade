"""End-to-end proof that Section 13's flowchart works as a real state
machine: a hand-constructed EUR/USD day (bullish H1 bias, a clean Asia-low
sweep in the LKZ, a displacement CHoCH leaving an FVG+OB, a retracement
that fills the resting limit at the OB per the Example-A nuance, a TP1
hit with break-even applied, and a hard-flat close at 19:30 GMT) is
replayed candle-by-candle through the real `InstrumentEngine`,
`OrderManager`, and `BacktestExecutionAdapter` — the exact same classes
production trading uses, per docs/STRATEGY_INTEGRITY.md.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from m5_reversal_bot.core.enums import CloseReason, Instrument, Mode, TradeStatus
from m5_reversal_bot.execution.backtest_adapter import BacktestExecutionAdapter
from m5_reversal_bot.execution.order_manager import OrderManager
from m5_reversal_bot.persistence import db as db_module
from m5_reversal_bot.strategy.engine import EngineDependencies, InstrumentEngine
from m5_reversal_bot.strategy.risk import AccountSnapshot
from tests.conftest import make_candle

GMT = timezone.utc


def _flat(t, price=1.1035, wiggle=0.00002):
    return make_candle(Instrument.EURUSD, "M5", t, price, price + wiggle, price - wiggle, price)


def build_h1_series():
    start = datetime(2025, 1, 5, 20, 0, tzinfo=GMT)
    rows = [
        (1.0995, 1.0993, 1.1000, 1.0998),
        (1.0999, 1.0997, 1.1005, 1.1003),
        (1.1004, 1.1002, 1.1010, 1.1008),
        (1.1009, 1.1007, 1.1015, 1.1013),
        (1.1015, 1.1012, 1.1050, 1.1030),  # swing high candidate: high=1.1050
        (1.1019, 1.1018, 1.1020, 1.1019),
        (1.1020, 1.1017, 1.1025, 1.1022),
        (1.1026, 1.1024, 1.1065, 1.1060),  # BOS: close 1.1060 > 1.1050 -> bullish H1
        (1.1058, 1.1055, 1.1070, 1.1065),
        (1.1062, 1.1060, 1.1075, 1.1070),
    ]
    candles = []
    for i, (o, l, h, c) in enumerate(rows):
        candles.append(make_candle(Instrument.EURUSD, "H1", start + timedelta(hours=i), o, h, l, c))
    return candles


def build_m5_series():
    day_start = datetime(2025, 1, 6, 0, 0, tzinfo=GMT)
    candles = []
    t = day_start

    def add(o, h, l, c):
        nonlocal t
        candles.append(make_candle(Instrument.EURUSD, "M5", t, o, h, l, c))
        t += timedelta(minutes=5)

    # Asia session 00:00-06:00 (72 candles): flat, with one clean high and one clean low.
    for _ in range(20):
        add(1.1035, 1.10352, 1.10348, 1.1035)
    add(1.1035, 1.1050, 1.1033, 1.1036)          # Asia high = 1.1050
    for _ in range(20):
        add(1.1035, 1.10352, 1.10348, 1.1035)
    add(1.1035, 1.10352, 1.1020, 1.1034)         # Asia low = 1.1020 (high kept flat: no spurious swing-high fractal)
    for _ in range(30):
        add(1.1035, 1.10352, 1.10348, 1.1035)
    assert len(candles) == 72

    # 06:00-07:00 filler (12 candles).
    for _ in range(12):
        add(1.1035, 1.10352, 1.10348, 1.1035)
    assert len(candles) == 84
    assert t == datetime(2025, 1, 6, 7, 0, tzinfo=GMT)

    # LKZ price action: quiet -> dip -> sweep -> bounce (local swing high)
    # -> pullback (leaves the OB) -> displacement CHoCH+FVG -> retrace
    # into the OB (taking an inducement swing out on the way) -> fill.
    for _ in range(6):
        add(1.1035, 1.10355, 1.10348, 1.1035)          # r0-r5: 07:00-07:25
    add(1.1035, 1.10355, 1.1028, 1.1029)                # r6  07:30 dip start
    add(1.1029, 1.1030, 1.1013, 1.1022)                 # r7  07:35 SWEEP (Asia low 1.1020)
    add(1.1022, 1.1040, 1.1021, 1.1038)                 # r8  07:40 local swing high (1.1040)
    add(1.1038, 1.1039, 1.1025, 1.1027)                 # r9  07:45
    add(1.1027, 1.1029, 1.1020, 1.1023)                 # r10 07:50
    add(1.1023, 1.1025, 1.1018, 1.1020)                 # r11 07:55 OB candle (bearish, 1.1018-1.1025)
    add(1.1020, 1.1055, 1.1019, 1.1052)                 # r12 08:00 DISPLACEMENT + CHoCH (close > 1.1040)
    add(1.1052, 1.1054, 1.1048, 1.1050)                 # r13 08:05 (FVG candle3: low 1.1048 > r11 high 1.1025)
    add(1.1050, 1.1051, 1.1042, 1.1043)                 # r14 08:10
    add(1.1043, 1.1044, 1.1033, 1.1036)                 # r15 08:15 inducement swing low (1.1033)
    add(1.1036, 1.1040, 1.1035, 1.1038)                 # r16 08:20
    add(1.1038, 1.1041, 1.1036, 1.1039)                 # r17 08:25
    add(1.1039, 1.1040, 1.1030, 1.1035)                 # r18 08:30
    add(1.1035, 1.1036, 1.1024, 1.1034)                 # r19 08:35
    add(1.1034, 1.1035, 1.1017, 1.1033)                 # r20 08:40 FILL (low <= entry 1.10215)
    add(1.1033, 1.1042, 1.1032, 1.1040)                 # r21 08:45
    add(1.1040, 1.1049, 1.1039, 1.1047)                 # r22 08:50
    add(1.1047, 1.1052, 1.1046, 1.1050)                 # r23 08:55 TP1 hit (high >= 1.1048)

    # Jump straight to the 19:30 GMT hard-flat boundary.
    candles.append(make_candle(Instrument.EURUSD, "M5", datetime(2025, 1, 6, 19, 30, tzinfo=GMT), 1.1045, 1.1046, 1.1044, 1.1045))

    return candles


@pytest.fixture
def wired_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    db_module._engine = None
    db_module._SessionLocal = None
    db_module.init_db()

    adapter = BacktestExecutionAdapter(
        initial_equity=10_000.0,
        spread_model={"EURUSD": 0.00007},
        slippage_model={"EURUSD": 0.0},
    )
    adapter.connect()

    snapshot = AccountSnapshot(
        equity_start_of_day=10_000.0, equity_current=10_000.0, high_water_mark_month=10_000.0,
        daily_realized_loss_percent=0.0, weekly_realized_loss_percent=0.0,
        consecutive_losses_this_session=0, consecutive_losses_running=0,
        trades_this_kill_zone=0, trades_today=0, concurrent_positions_total=0,
        concurrent_positions_by_instrument={}, combined_open_risk_percent=0.0,
        live_trades_taken_lifetime=41, in_recovery_mode=False, monthly_drawdown_percent=0.0,
        monthly_brake_active=False, demo_requalification_trades_done=0,
    )

    deps = EngineDependencies(
        news_events_provider=lambda _t: [],
        holiday_calendar={},
        account_snapshot_provider=lambda: snapshot,
        reference_candles_provider=lambda: [],
        current_spread_provider=lambda: 0.00007,
        bracket_order_supported=lambda: True,
    )
    engine = InstrumentEngine(Instrument.EURUSD, Mode.BACKTEST, deps)
    order_manager = OrderManager(adapter, Mode.BACKTEST, account_id=None)
    return engine, order_manager, adapter


def test_full_sweep_to_hard_flat_cycle(wired_engine):
    engine, om, adapter = wired_engine

    for h1_candle in build_h1_series():
        engine.process_h1_candle(h1_candle)

    m5_candles = build_m5_series()

    submitted = False
    filled = False
    tp1_hit = False
    closed = False

    with db_module.session_scope() as s:
        for candle in m5_candles:
            # Resolve fills/stops/TPs against already-resting orders using
            # THIS bar's range before the engine reacts to this bar's own
            # close — see backtest/engine.py for why the order matters.
            fill_events = adapter.advance_bar(candle)
            for ev in fill_events:
                if ev["type"] == "FILLED":
                    filled = True
                elif ev["type"] == "TP_HIT":
                    tp1_hit = True
                om._translate_event(ev, engine, s)

            actions = engine.process_m5_candle(candle)
            om.handle_actions(actions, s)
            if any(a.type == "SUBMIT_BRACKET_ORDER" for a in actions):
                submitted = True

            if engine.active_trade is not None and engine.active_trade.status == TradeStatus.CLOSED:
                closed = True

    assert submitted, "expected the scored setup to clear the bar and submit a bracket order"
    assert filled, "expected the resting limit to fill on the retracement"
    assert tp1_hit, "expected price to reach TP1"

    # The trade object is cleared from `active_trade` once closed; recover
    # it via the order manager's DB id map for final assertions.
    assert len(om._db_id_by_trade) == 1
    with db_module.session_scope() as s:
        from m5_reversal_bot.persistence.schema import TradeRecord

        rec = s.get(TradeRecord, list(om._db_id_by_trade.values())[0])
        assert rec.status == "CLOSED"
        assert rec.close_reason == CloseReason.HARD_FLAT.value
        assert rec.be_applied is True
        assert rec.entry_price == pytest.approx(1.10215, abs=1e-5)
        assert rec.tp1_price == pytest.approx(1.1048, abs=1e-4)
        assert rec.r_result is not None
        # Half the position banked ~+2.25R at TP1; blended result should be positive.
        assert rec.r_result > 0
        assert rec.rule_compliance is True
