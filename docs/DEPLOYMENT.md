# Deployment

## Platform requirement: MT5 API needs Windows

The bot connects to your broker exclusively through the official
`MetaTrader5` python package (`execution/mt5_adapter.py`,
`data/mt5_feed.py`) — the MT5 **API**, not the desktop terminal UI. No
manual clicking, no terminal automation. That package only ships
prebuilt wheels for Windows, because it talks to the MT5 terminal process
via a local IPC channel that only exists on Windows (or under Wine). Set
`MT5_BRIDGE_MODE=mt5linux` (default `local`) to instead reach a *remote*
MT5 terminal over the `mt5linux` bridge — this is what lets a plain Linux
host run PAPER/DEMO/LIVE with zero Wine installed on itself (see
"All-Linux via the mt5linux bridge" below); Wine still exists, just
inside a separate container.

| Mode | Needs MT5 API | Platform (`bridge_mode=local`) | Platform (`bridge_mode=mt5linux`) |
|---|---|---|---|
| BACKTEST | No (CSV history) | Any (Linux/macOS/Windows, incl. Docker) | n/a |
| PAPER | Yes (read-only price feed) | Windows or Wine on this host | Any host — Wine lives in the bridge container |
| DEMO | Yes (real orders, demo account) | Windows or Wine on this host | Any host — Wine lives in the bridge container |
| LIVE | Yes (real orders, funded account) | Windows or Wine on this host | Any host — Wine lives in the bridge container |

**Recommended layouts:**

1. **Everything on Windows** (simplest, most reliable): install Python
   3.11+, MT5 terminal, and this repo directly on a Windows Server / VM.
   Run `scripts/run_demo.py` or `scripts/run_live.py` there. The
   dashboard is still just a browser tab — connect to it from any
   machine. `MT5_BRIDGE_MODE=local` (the default).
2. **Split deployment, Windows VPS**: run BACKTEST/reporting and the
   dashboard from the Linux Docker image (`docker/`); run the DEMO/LIVE
   process on a small Windows VM pointed at the same Postgres database
   (`docker-compose.prod.yml`), so both share one trade history.
   `MT5_BRIDGE_MODE=local` on the Windows side.
3. **All-Linux, via a Dockerized Wine bridge**: keep the whole fleet on
   Linux by running a second container (`docker/mt5-bridge/`) that owns
   Wine + the MT5 terminal + the `mt5linux` RPyC bridge; the main app
   container talks to it over the network with
   `MT5_BRIDGE_MODE=mt5linux` and never touches Wine itself. See
   "All-Linux via the mt5linux bridge" below — this trades "manage a
   Windows box" for "manage a Wine container," which is real work of a
   different kind, not free simplicity.

## All-Linux via the mt5linux bridge

```bash
cd docker
cp ../.env.example ../.env
# edit .env: MT5_LOGIN/MT5_PASSWORD/MT5_SERVER, and set:
#   MT5_BRIDGE_MODE=mt5linux
#   MT5_BRIDGE_HOST=mt5-bridge
#   MT5_BRIDGE_PORT=8001
docker compose -f docker-compose.yml -f docker-compose.mt5-bridge.yml up -d --build
docker compose logs -f mt5-bridge     # first build takes a while — Wine + MT5 + a Python install, all inside the image
```

Credentials can also be entered (or changed) live from the dashboard's
**Broker Connection** panel instead of editing `.env` — see
`docs/API.md`. Either way, login happens purely through
`initialize()`/`login()` API calls; nothing here scripts a GUI click, in
local mode or bridge mode.

**Be honest with yourself about this path before committing to it:**

- `docker/mt5-bridge/Dockerfile` follows the well-documented community
  recipe for MT5-under-Wine (Xvfb virtual display, WineHQ's own
  packages, `mt5linux` as the bridge — the same shape as community images
  like `gmag11/MetaTrader5-docker-image`), but it has **not** been
  end-to-end verified against a live broker connection in this
  repository — there's no Windows/Wine available to test it here. Expect
  to iterate against your specific broker's terminal build.
- Most brokers ship their own branded MT5 installer (to preselect their
  server list) — point the `MT5_SETUP_URL` build arg at it instead of the
  generic MetaQuotes one if yours does.
- Wine + a GUI Windows app in a container is inherently more fragile than
  either a real Windows VPS or a paid cloud bridge: expect occasional
  Wine crashes, and re-verify after MT5 terminal updates.
- The Wine prefix (terminal install + any session state) persists in the
  `mt5-wine-prefix` Docker volume, so you don't repeat the install on
  every restart — but back it up like anything else stateful.

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

See `.env.example` for the full list. `MT5_LOGIN`/`MT5_PASSWORD`/
`MT5_SERVER` can be set here as startup defaults, or entered/changed live
through the dashboard's **Broker Connection** panel (`POST
/api/bot/broker-connect`) without editing this file or restarting.
Everything else (mode, enabled instruments, poll cadence) lives in
`config/config.yaml` and is editable live through the dashboard's
Configuration Management control (or `PUT /api/config/`).

Set `DASHBOARD_USERNAME`/`DASHBOARD_PASSWORD` to require HTTP Basic Auth
across the whole app (dashboard + API + WebSocket) — recommended once
real broker credentials start flowing through the Broker Connection
panel. Leave both blank to run open (fine behind your own VPN/reverse
proxy, the existing default).

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
