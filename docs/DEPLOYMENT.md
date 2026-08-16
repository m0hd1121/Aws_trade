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

Full details, architecture diagram, configuration, and
troubleshooting live in [`docker/mt5-bridge/README.md`](../docker/mt5-bridge/README.md) — this section is the short version.

One command from the repo root:

```bash
./setup.sh
```

This copies `.env.example` → `.env` if missing, forces
`MT5_BRIDGE_MODE`/`HOST`/`PORT` to match the compose topology
(`mt5-bridge` on the internal Docker network), and runs both compose
files together (`docker-compose.yml` + `docker-compose.mt5-bridge.yml`)
with `--build`. It does **not** need your MT5 credentials to run —
those are entered afterward from the dashboard's **Broker Connection**
panel (`http://localhost:8000`), which talks to the MT5 API directly via
`initialize()`/`login()` calls — no GUI/VNC step, in local mode or
bridge mode. `./setup.sh --no-bridge` skips the Wine image if you only
need BACKTEST/dashboard, or already reach MT5 some other way.

Equivalent by hand, if you'd rather not run the script:

```bash
cd docker
cp ../.env.example ../.env
# edit .env: MT5_BRIDGE_MODE=mt5linux, MT5_BRIDGE_HOST=mt5-bridge, MT5_BRIDGE_PORT=8001
docker compose -f docker-compose.yml -f docker-compose.mt5-bridge.yml up -d --build
docker compose logs -f mt5-bridge     # the MT5 terminal installs on FIRST BOOT, into the persisted volume
```

**Be honest with yourself about this path before committing to it:**

- `docker/mt5-bridge/Dockerfile` follows the well-documented community
  recipe for MT5-under-Wine (Xvfb virtual display, `mt5linux` as the
  bridge), with structure adapted from
  [`lucas-campagna/mt5linux@docker-image-optimization`](https://github.com/lucas-campagna/mt5linux/tree/docker-image-optimization/docker).
  It has **not** been end-to-end verified against a live broker
  connection in this repository — there's no Docker daemon or broker
  account available to test it here. Expect to iterate against your
  specific broker's terminal build. The base image is Debian on purpose:
  on Alpine's musl-based Wine, `import MetaTrader5` hangs indefinitely
  inside the Wine-side Python, while everything else works. Wine itself is
  further pinned to a specific version (9.0), because the generic MT5
  installer's anti-tamper check fails under newer Wine — see
  docker/mt5-bridge/README.md for both.
- Most brokers ship their own branded MT5 installer (to preselect their
  server list) — set the `MT5_SETUP_URL` environment variable to it
  instead of the generic MetaQuotes one if yours does. It's read on the
  bridge's **first boot**, so changing it later means removing the
  `mt5-wine-prefix` volume and restarting, not rebuilding.
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
between candle closes; `docker-compose.yml` caps the `m5-bot` container at
320MB / 1 CPU as a sane default, `docker-compose.prod.yml` at 384MB /
0.75 CPU.

### Running the mt5linux bridge on a 1GB host

The bridge is the expensive part — Wine plus a real MT5 terminal plus a
second Wine-side Python, not the tens of MB the app itself needs. On a
1GB droplet there is close to zero margin once you add it up:

| Component | Budget |
|---|---|
| OS + Docker daemon | ~150-250MB |
| `m5-bot` container | 320MB cap (`docker-compose.yml`) |
| `mt5-bridge` container | 1200MB cap (`docker-compose.mt5-bridge.yml`) |
| **Total** | **~1.7-1.8GB against 1GB physical** |

The bridge's cap is sized for its peak (the MT5 install plus the Visual
C++ redistributable install that `MetaTrader5`'s Python package turns out
to actually need — see `docker/mt5-bridge/README.md`), not its steady
state, and leans on swap to cover the deficit above. It stops
`explorer.exe`/`plugplay.exe` once the terminal is up to keep steady-state
usage down. It also defers the Wine prefix init and the MT5 install
from build time to first boot, into the persisted `mt5-wine-prefix`
volume — so the heavy one-time work can fail and be retried with a
container restart instead of taking a 20-minute image build down with it.
See [`docker/mt5-bridge/README.md`](../docker/mt5-bridge/README.md).

That's a deficit by design, covered by swap rather than physical RAM —
swap absorbs the *bursts* (the bridge image's build, and the MT5
terminal's own startup), it isn't meant to carry sustained working set
(active swapping is slow and will make candle processing lag). `./setup.sh`
now provisions a 2GB swap file automatically on low-RAM hosts with none
active; to do it by hand:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && \
  sudo mkswap /swapfile && sudo swapon /swapfile && \
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo sysctl -w vm.swappiness=10   # prefer RAM, but don't refuse to use swap
```

Two more things `./setup.sh` does for the same reason:

- Builds `m5-bot` and `mt5-bridge` **sequentially**, not via `--build`'s
  default parallel buildx bake — building both at once roughly doubles
  peak build-time RAM (pip wheel builds alongside apk/Wine)
  and is what OOM-killed an earlier attempt of this on a 512MB host.
- Runs the bridge container with `WINEDEBUG=-all` (the Dockerfile's own
  build-time default stays `fixme-all`, useful if a rebuild needs
  debugging) — Wine's fixme/warn logging isn't free, and on a slow
  `wineboot` it was visibly spinning on OLE/RPC warning noise, i.e. CPU a
  small host doesn't have to spare.

If the bridge still won't build reliably even with these in place, the
most honest fix is to stop asking a 1GB box to do it: build the
`m5-mt5-bridge` image (or just run the build) on a bigger machine once,
`docker save`/`docker load` it onto the droplet, and let the small host
only ever *run* the containers, never build them.

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

## Exposing the dashboard safely

The dashboard accepts live broker credentials, so how it's reachable
matters. Three options, strongest first:

**1. SSH tunnel (recommended if you're not using Cloudflare).** Set
`DASHBOARD_BIND=127.0.0.1` in `.env` and the port is published only on
the VPS's loopback — nothing is reachable from the internet at all. From
your own machine:

```bash
ssh -N -L 8000:localhost:8000 root@your-vps    # leave running
# then open http://localhost:8000 locally
```

No open port, no shared password, no third party. The cost is that you
need the SSH session up while you're watching the dashboard.

**2. Cloudflare Tunnel** — see below. Similar security, more convenient
(a normal URL, SSO), at the cost of routing through Cloudflare.

**3. Public port + Basic Auth.** `DASHBOARD_BIND=0.0.0.0` (the default)
with `DASHBOARD_USERNAME`/`DASHBOARD_PASSWORD` set. Workable, but it's a
single shared secret over plain HTTP — pair it with a firewall
restricting port 8000 to your own IP:

```bash
ufw allow OpenSSH
ufw allow from YOUR.HOME.IP.ADDR to any port 8000 proto tcp
ufw --force enable
```

Never run `DASHBOARD_BIND=0.0.0.0` with the auth variables blank.

### Cloudflare Tunnel

Basic Auth over plain HTTP on a public port is a stopgap: one shared
secret, sent in a reversible encoding, on a port anyone can find. Since
that panel accepts live broker credentials, prefer a tunnel:

```bash
./setup.sh --tunnel
```

This adds a `cloudflared` container and **stops publishing port 8000 on
the host entirely** — the droplet makes an outbound connection to
Cloudflare and traffic returns down it, so there is no inbound port to
scan. Free tier is sufficient. It needs `CLOUDFLARE_TUNNEL_TOKEN` in
`.env`; the setup steps are in the header of
[`docker/docker-compose.cloudflared.yml`](../docker/docker-compose.cloudflared.yml).

Two things worth knowing:

- Put **Cloudflare Access** in front of the hostname (Zero Trust → Access
  → Applications → self-hosted). That authenticates viewers with SSO or
  email OTP *before* any request reaches this app, which is a genuine
  improvement over a shared password rather than a second copy of one.
  The dashboard's WebSocket works through both Tunnel and Access.
- Requires Docker Compose **2.24+**. The overlay closes the port with
  `ports: !reset []`, and older Compose silently ignores that tag —
  leaving the port open while appearing to work. `setup.sh --tunnel`
  checks the version and refuses rather than half-applying it.

Costs about 30-50MB RAM (capped at 96MB), which is affordable even in the
1GB budget above.

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
