# Deployment

## Platform requirement: MT5 API needs Windows

The bot connects to your broker exclusively through the official
`MetaTrader5` python package (`execution/mt5_adapter.py`,
`data/mt5_feed.py`) — the MT5 **API**, not the desktop terminal UI. No
manual clicking, no terminal automation. But that package only ships
prebuilt wheels for Windows, because it talks to the MT5 terminal process
via a local IPC channel that only exists on Windows (or under Wine).

| Mode | Needs MT5 API | Platform |
|---|---|---|
| BACKTEST | No (CSV history) | Any (Linux/macOS/Windows, incl. Docker) |
| PAPER | Yes (read-only price feed) | Windows or Wine |
| DEMO | Yes (real orders, demo account) | Windows or Wine |
| LIVE | Yes (real orders, funded account) | Windows or Wine |

**Recommended layouts:**

1. **Everything on Windows** (simplest): install Python 3.11+, MT5
   terminal, and this repo directly on a Windows Server / VM. Run
   `scripts/run_demo.py` or `scripts/run_live.py` there. The dashboard is
   still just a browser tab — connect to it from any machine.
2. **Split deployment**: run BACKTEST/reporting and the dashboard's static
   assets from the Linux Docker image (`docker/`); run the DEMO/LIVE
   process on a small Windows VM pointed at the same Postgres database
   (`docker-compose.prod.yml`), so both share one trade history.
3. **Wine**: the `MetaTrader5` package and terminal do run under Wine on
   Linux for teams that want a single Linux fleet; treat this as
   supported-but-unofficial and test thoroughly before trusting it live.

## Local development (any platform, BACKTEST/dashboard only)

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # fill in DB path, leave MT5_* blank
python scripts/init_db.py
python scripts/run_backtest.py --instruments EURUSD --start 2024-01-01 --end 2024-06-30
uvicorn m5_reversal_bot.api.main:app --reload --app-dir src
# open http://localhost:8000
```

## Windows (DEMO/LIVE)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# edit .env: MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, MT5_TERMINAL_PATH
python scripts\init_db.py
python scripts\run_demo.py            # or run_live.py once validated
```

The MT5 terminal must be installed and, the first time, logged in once
manually so Windows trusts it; after that `MetaTrader5.initialize()` /
`.login()` drive it headlessly.

## Docker (BACKTEST/dashboard image)

```bash
cd docker
cp ../.env.example ../.env
docker compose up -d --build
docker compose logs -f
# http://localhost:8000
```

Production overlay (Postgres, tighter resource caps, no host port):

```bash
export POSTGRES_PASSWORD=change-me
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Put your own reverse proxy (Caddy/Nginx/Traefik) in front for TLS; the
app itself only serves plain HTTP.

## Resource footprint

No GPU, no ML runtime, no headless browser, no message broker. Steady
state is: one Python process, SQLite (or a small Postgres), and a
handful of MB of rolling M5/H1 candle buffers per instrument
(`data/candle_aggregator.py` caps each instrument's window at ~4500 M5 /
500 H1 / 200 H4 candles). Expect well under 200MB RSS and negligible CPU
between candle closes; `docker-compose.yml` caps the container at 512MB /
1 CPU as a sane default, `docker-compose.prod.yml` at 384MB / 0.75 CPU.

## Environment variables

See `.env.example` for the full list. The only required ones for
DEMO/LIVE are `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`. Everything else
(mode, enabled instruments, poll cadence) lives in `config/config.yaml`
and is editable live through the dashboard's Configuration Management
control (or `PUT /api/config/`) without a restart.

## Health checks

- `GET /api/healthz` — process liveness.
- `GET /api/dashboard/connection-health` — data feed / broker adapter
  status, as recorded by `monitoring/health.py` and polled every tick.
- The Docker image's `HEALTHCHECK` hits `/api/healthz` every 30s.

## Backups

The entire trading state (trades, setups, skips, logs, AI insights) lives
in one database. For SQLite, back up the file at
`./data/m5_bot.db` (or the Docker volume `m5-data`) on whatever schedule
your risk tolerance demands; for Postgres, use standard `pg_dump` /
managed-backup tooling against the `m5bot` database.

## Upgrading

1. Pull the new code.
2. Run `python scripts/init_db.py` (additive schema changes only —
   SQLAlchemy's `create_all` never drops or alters existing tables; a
   genuine breaking schema change ships its own migration script).
3. Restart the process/container. The broker itself still holds any open
   position/pending order regardless of whether this process is running —
   a restart does not touch your actual exposure. Note the current
   limitation: `InstrumentEngine`'s in-memory state (which trade it
   thinks is active, KZ progress) is not yet reconstructed from the
   database on startup, so restarting mid-trade means the engine won't
   resume managing that specific position's BE/trailing until you extend
   `BotRunner._build_components` to rehydrate `active_trade` from
   `persistence.repository.list_open_trades` on boot. Avoid restarting
   the live process while a trade is open until that's added; prefer
   restarting between kill zones.
