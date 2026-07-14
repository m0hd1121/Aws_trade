# Architecture

## Design principle

**One decision-making code path.** `strategy/engine.py::InstrumentEngine`
is the only place a trading decision gets made, and it is completely
adapter-agnostic — it never imports anything from `execution/`, `data/`,
or `persistence/`. Backtest, paper, demo, and live trading all replay
candles through the same `InstrumentEngine` instance type and the same
`execution/order_manager.py::OrderManager`; only the `ExecutionAdapter`
and `MarketDataFeed` implementations underneath differ. This is what
makes "the same strategy logic is used across backtesting, paper trading,
demo trading, and live trading" true by construction rather than by
convention.

## Module map

```
src/m5_reversal_bot/
├── core/            Domain models, enums, frozen strategy constants,
│                     GMT clock utilities, operational config.
├── strategy/         The rulebook, verbatim, as pure functions + the
│                     InstrumentEngine state machine (Section 13). No
│                     I/O, no broker calls, no persistence — 100% testable
│                     in isolation. See docs/STRATEGY_INTEGRITY.md.
├── data/             Market data feeds (MT5 live/demo, historical CSV for
│                     backtests) behind one MarketDataFeed interface.
├── execution/         Broker adapters (MT5, paper-simulated, backtest-
│                     simulated) behind one ExecutionAdapter interface,
│                     plus order_manager.py which bridges engine actions
│                     to adapter calls and persists every state change.
├── risk_manager/      Mutable account/session state (equity, daily/
│                     weekly loss, consecutive losses, trade counts) —
│                     the stateful counterpart to strategy/risk.py's pure
│                     rule functions.
├── ai/               Analytics, execution-quality scoring, anomaly
│                     detection. Read-only relative to strategy/*: see
│                     the AI boundary in docs/STRATEGY_INTEGRITY.md.
├── persistence/       SQLAlchemy schema + repository functions. SQLite by
│                     default; Postgres via DATABASE_URL for production.
├── backtest/          Event-driven replay harness + performance reports,
│                     built entirely on strategy/execution/persistence —
│                     no duplicated logic.
├── bot/              BotController (the state machine behind every
│                     dashboard control) and BotRunner (the async polling
│                     loop for PAPER/DEMO/LIVE).
├── monitoring/         Structured logging, connection health, alerting.
└── api/               FastAPI REST + WebSocket surface for the dashboard.

dashboard/            Static HTML/CSS/JS — no build step, no framework.
docs/strategy/        The frozen rulebook (hash-locked, see above).
```

## Data flow (one M5 candle, PAPER/DEMO/LIVE)

```
MarketDataFeed.get_recent_candles()
        │
        ▼
CandleAggregator (rolling window, dedupes to "newly closed" candles)
        │
        ▼
InstrumentEngine.process_m5_candle(candle)
   Section 13 flowchart: daily lockout → map marking (06:45 GMT) →
   kill-zone gating → D1-D7 → sweep search → CHoCH search → chop/news →
   score → construct → checklist → submit/void/skip
        │  (returns a list of EngineAction — never touches a broker)
        ▼
OrderManager.handle_actions(actions, db_session)
   Persists setups/trades/events, calls the ExecutionAdapter for anything
   with broker-side effect (submit, cancel, modify stop/target, close)
        │
        ▼
ExecutionAdapter (MT5 / Paper / Backtest)
        │
        ▼
OrderManager.poll_fills() → translates fill/stop/TP events back into
InstrumentEngine.on_order_filled / on_tp1_filled / on_trade_closed calls,
whose resulting EngineActions flow back through handle_actions() again.
```

Backtest mode runs the identical `process_m5_candle` → `handle_actions` →
adapter loop, just fed by `data/historical_loader.py` instead of a live
feed, bar-by-bar instead of on a poll timer (`backtest/engine.py`).

## Why a stage machine, not a callback pile

`InstrumentEngine.stage` (a `StrategyStage` enum) is updated at every
meaningful transition and persisted to `strategy_stage_log` on every
change. This is what powers the dashboard's "what is the bot doing right
now, and why" panel — the same enum a developer reads in `engine.py` is
exactly what the operator sees live.

## Storage

SQLite by default (`DATABASE_URL=sqlite:///./data/m5_bot.db`) — zero
external dependency, appropriate for a single-process bot on modest
hardware. Point `DATABASE_URL` at Postgres for multi-instance or
high-durability deployments; no code changes required (SQLAlchemy).

Every trade has an append-only `trade_events` audit trail
(`persistence/schema.py::TradeEvent`) — every state transition a trade
goes through is a separate row, never updated or deleted, so any trade is
fully reconstructable and auditable after the fact.

## Extending the system

New features should slot into existing seams without touching
`strategy/*`:

- A new dashboard panel: add a route to `api/routes_dashboard.py` and a
  section to `dashboard/index.html` + `dashboard/js/app.js`.
- A new broker: implement `execution/broker_interface.py::ExecutionAdapter`.
- A new data source: implement `data/feed.py::MarketDataFeed`.
- A new AI insight: add to `ai/*`, write via `ai/insights_store.py` — it
  cannot reach `strategy/*` by construction (see the AI boundary test).

If a change requires touching a file under `strategy/`, stop and check
whether it's actually a strategy-rule change (which requires the
rulebook-hash update procedure in docs/STRATEGY_INTEGRITY.md) or an
engineering/orchestration fix (like the timing and swing-reference fixes
documented in the test suite's commit history) that doesn't alter any
numbered rule.
