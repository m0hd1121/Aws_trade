# M5 Liquidity Reversal Bot

A production-grade automated trading system implementing **The M5
Liquidity Reversal Playbook** — a mechanical, zero-discretion price-action
system for EUR/USD and XAU/USD during the London and New York Kill Zones
— exactly as specified, with backtesting, paper trading, demo trading,
live trading (via the MetaTrader 5 API), a real-time dashboard, and
self-learning analytics that can never touch a strategy rule.

The full rulebook is frozen at [`docs/strategy/M5_Liquidity_Reversal_Playbook.md`](docs/strategy/M5_Liquidity_Reversal_Playbook.md)
and hash-verified at every process start — see
[`docs/STRATEGY_INTEGRITY.md`](docs/STRATEGY_INTEGRITY.md) for the
mechanism and what to do if the strategy legitimately needs to change.

## What's in here

- **`src/m5_reversal_bot/strategy/`** — the rulebook, transcribed module
  by module (swings/CHoCH, sweeps, displacement/FVG, order blocks, POI,
  inducement, chop, SMT, sessions/D1-D7, the 12-point scoring model,
  entry/stop/exit/risk rules, absolute filters, the 15-point checklist)
  into pure, independently-testable functions, orchestrated by
  `engine.py` as the exact Section 13 decision flowchart.
- **`src/m5_reversal_bot/execution/`** — MT5 (live/demo), paper, and
  backtest execution adapters behind one interface, so the strategy
  literally cannot tell which mode it's running in.
- **`src/m5_reversal_bot/backtest/`** — event-driven historical replay +
  performance reporting, using the same engine as live trading.
- **`src/m5_reversal_bot/ai/`** — performance analytics, execution-quality
  scoring, and data-quality anomaly detection. Architecturally unable to
  influence a trading decision (enforced by
  `tests/unit/test_ai_boundary.py`).
- **`src/m5_reversal_bot/api/` + `dashboard/`** — a FastAPI backend and a
  dependency-free HTML/CSS/JS dashboard: live bot status and
  step-by-step "what is it doing right now" transparency, positions,
  trade history, P&L/drawdown, risk metrics, system health, and every
  bot control (Start/Stop/Pause/Resume/Restart/Reset Session/Emergency
  Stop/Manual Refresh/Configuration).
- **`tests/`** — unit tests per rule (including the exact arithmetic from
  Section 11's three worked examples), an AI/strategy boundary test, a
  strategy-integrity hash test, and a full end-to-end integration test
  that replays a hand-built trading day through the real engine from
  sweep to fill to TP1/break-even to hard-flat close.

## Quick start — one command (Linux, all-in, no Wine on your host)

```bash
./setup.sh
```

Builds and starts the app **and** a Dockerized Wine+MT5 bridge
(`docker/mt5-bridge/`) together, so PAPER/DEMO/LIVE trading works on a
plain Linux VPS with zero Wine installed on it directly. Open
`http://localhost:8000`, enter your MT5 login/password/server in the
dashboard's **Broker Connection** panel (talks to the MT5 API directly —
no GUI/VNC step), then click Start Bot. First build is slow (Wine + the
MT5 terminal + a Python install, all inside the bridge image — often
15-30+ minutes); everything after that is fast.

Just want BACKTEST + the dashboard, or already running MT5 elsewhere
(Windows VPS, `bridge_mode=local`)? `./setup.sh --no-bridge` skips the
Wine image entirely.

## Quick start — manual (backtest + dashboard, any platform)

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/init_db.py
uvicorn m5_reversal_bot.api.main:app --reload --app-dir src
# → http://localhost:8000
```

Run a backtest:

```bash
python scripts/run_backtest.py --instruments EURUSD,XAUUSD \
    --start 2024-01-01 --end 2024-12-31 --data-dir ./data/history
```

For DEMO/LIVE without Docker you need a Windows host, or Wine on this
one (`bridge_mode=local`) — see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
for the full platform story and resource footprint notes.

```bash
python scripts/run_paper.py   # simulated fills, real prices, no real orders
python scripts/run_demo.py    # real orders on a demo MT5 account
python scripts/run_live.py    # real orders on a funded MT5 account
```

None of these auto-start trading — the process comes up idle; you start
it from the dashboard (or `POST /api/bot/start`) once you've confirmed
mode/config, or pass `--autostart`.

## Tests

```bash
PYTHONPATH=src pytest tests/ -v
```

44 tests, including the literal arithmetic from Section 11's Examples
A/B/C (the POI fallback nuance, the 8/12 spine-broken rejection, the
10/12-killed-by-D1-filter case), Section 8.1's worked position-sizing
examples, and a full sweep→CHoCH→score→fill→TP1→BE→hard-flat replay
through the production engine.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module map, data flow, extension points.
- [`docs/STRATEGY_INTEGRITY.md`](docs/STRATEGY_INTEGRITY.md) — the freeze mechanism, the AI boundary, recalibration.
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — platforms, Docker, resource footprint, backups.
- [`docs/API.md`](docs/API.md) — full REST/WebSocket reference.

## Honest performance expectations

Per the rulebook's own Section 12: 35-45% win rate, ~2.2-2.6R blended
average winner, +0.25R to +0.45R expectancy per trade after costs, with
5+ consecutive losses expected roughly every ~80 trades. The dashboard's
Performance panel compares live results against these bands directly —
see `ai/analytics.py`. Validate on 60 demo/backtest trades at ≥95%
rule-compliance, then 40 live trades at 0.5% risk, before scaling to 1%
(Section 12.3, Section 8.2) — the bot enforces the risk-percent schedule
automatically via `risk_manager/account_state.py`.
