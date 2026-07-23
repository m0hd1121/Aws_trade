# MT5 Wine Bridge

Runs a real MetaTrader 5 terminal under Wine, in a container, and exposes
it over the [`mt5linux`](https://github.com/lucas-campagna/mt5linux) RPyC
bridge — so the main bot can run PAPER/DEMO/LIVE trading from a plain
Linux host with **zero Wine installed on that host**. Wine lives only in
this one container.

This exists because the official `MetaTrader5` Python package only ships
Windows wheels (it talks to the MT5 terminal via a local IPC channel that
only exists on Windows or under Wine). See the root
[`docs/DEPLOYMENT.md`](../../docs/DEPLOYMENT.md) for the full comparison
against a plain Windows VPS — this is a real alternative, not a strictly
better one.

## Quick start

From the repo root, one command builds and starts this alongside the
main app:

```bash
./setup.sh
```

That's it for most cases. Everything below is for when you want to
understand what's happening, customize it, or troubleshoot it.

## How it works

```
┌─────────────────────┐        mt5linux (RPyC)        ┌──────────────────────────┐
│  m5-bot container    │ ─────────────────────────────▶│  mt5-bridge container   │
│  (plain Linux)       │        tcp/8001                │  Xvfb + Wine + MT5      │
│  MT5_BRIDGE_MODE=     │                                │  terminal + wine-python │
│    mt5linux           │                                │  running mt5linux       │
└─────────────────────┘                                └──────────────────────────┘
```

- **Xvfb** gives Wine a virtual display — MT5's terminal is a GUI app
  even when driven purely through its API, so it needs *some* display
  target to run against, even headlessly.
- **Wine** (WineHQ's own Debian packages, not the older ones bundled with
  Debian) hosts an actual MT5 terminal install plus a Windows Python
  install with the real `MetaTrader5` package inside it.
- **mt5linux** runs an RPyC server under that Wine-side Python, exposing
  the exact same function calls (`initialize()`, `login()`,
  `copy_rates_from_pos()`, `order_send()`, etc.) over the network. The
  main app's `data/mt5_feed.py` / `execution/mt5_adapter.py` call these
  transparently — same code path as talking to a local `MetaTrader5`
  install, just proxied.
- Login happens purely through those API calls — **nothing here scripts
  a GUI click**. See the root README's Broker Connection panel section.

## Manual usage (without `./setup.sh`)

```bash
cd docker
docker compose -f docker-compose.yml -f docker-compose.mt5-bridge.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.mt5-bridge.yml logs -f mt5-bridge
```

Required `.env` settings (see `.env.example`):

```bash
MT5_BRIDGE_MODE=mt5linux
MT5_BRIDGE_HOST=mt5-bridge   # the compose service name — NOT 127.0.0.1
MT5_BRIDGE_PORT=8001
```

## Build arguments

| Arg | Default | Purpose |
|---|---|---|
| `MT5_SETUP_URL` | MetaQuotes' generic installer | Point this at your broker's own MT5 installer if they provide one — many require it to preselect their server list. |
| `WINE_PYTHON_URL` | Python 3.9.13 (64-bit) Windows installer | The Python version installed *inside* Wine, used only to run `mt5linux`'s server + the real `MetaTrader5` package. |

Override in `docker-compose.mt5-bridge.yml` under `build.args`, or via:

```bash
MT5_SETUP_URL=https://your-broker.com/mt5setup.exe \
  docker compose -f ../docker-compose.yml -f ../docker-compose.mt5-bridge.yml build mt5-bridge
```

## Troubleshooting

- **First build is slow (15-30+ minutes).** It's installing Wine, then
  MT5 terminal, then a full Windows Python, all inside the image. This
  is normal — check progress with `docker compose logs -f mt5-bridge`.
- **Build fails on the `wine mt5setup.exe /auto` step.** The silent-install
  flag is standard MT5 behavior, but installer builds vary. Try without
  `/auto` piped through a VNC viewer attached to the container's Xvfb
  display to see what's actually happening (`x11vnc` isn't included by
  default — add it temporarily if you need to look).
- **App reports "connection failed" via the Broker Connection panel.**
  Check `docker compose logs -f mt5-bridge` first — most failures are
  either the terminal not finishing its install, or wrong
  login/password/server. `MT5_BRIDGE_HOST` must be `mt5-bridge` (the
  compose service name), not `127.0.0.1` — that would point the app
  container at itself.
- **Wine crashes / the bridge stops responding.** `docker compose
  restart mt5-bridge`. The Wine prefix (terminal + settings) persists in
  the `mt5-wine-prefix` volume, so a restart doesn't repeat the install.
- **Build fails on `wine wineboot --init`** with `boot event wait timed
  out` / `could not load kernel32.dll, status c0000135`. This is Wine's
  own prefix-initialization handshake failing, not an MT5 problem — seen
  in practice on very small hosts (1 vCPU / 1GB RAM) where the handshake
  races CPU contention from the rest of the build. The Dockerfile already
  retries this step 3x and waits for Xvfb to actually accept connections
  (not a fixed sleep) before touching Wine, which resolves it on most
  hosts. If it still fails: give the build more headroom — stop other
  containers during the build, add swap (`fallocate -l 2G /swapfile &&
  chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile`), or build
  on a larger machine and just ship the resulting image / `mt5-wine-prefix`
  volume to the small host.

## Honest limitations

This follows the well-documented community pattern for MT5-under-Wine
(the same shape as images like `gmag11/MetaTrader5-docker-image`), but:

- It has **not** been end-to-end verified against a live broker
  connection in this repository — there was no Windows/Wine available
  to test it against while building this. Treat first boot as a real
  install against your specific broker.
- Wine running a GUI Windows app in a container is inherently more
  fragile than a real Windows VPS or a paid cloud MT5 bridge (e.g.
  MetaApi). Expect to re-verify after MT5 terminal updates.
- If anything here drifts from how `mt5linux` currently works, check
  https://github.com/lucas-campagna/mt5linux directly — that project is
  the source of truth for the bridge protocol itself, not this repo.

If this ends up being more maintenance than it's worth, a small Windows
VPS (`bridge_mode=local`) is the simpler, more reliable fallback — see
the root [`docs/DEPLOYMENT.md`](../../docs/DEPLOYMENT.md) for that path.
