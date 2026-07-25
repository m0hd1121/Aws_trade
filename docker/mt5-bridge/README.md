# MT5 Wine Bridge

Runs a real MetaTrader 5 terminal under Wine, in a small Alpine
container, and exposes it over the
[`mt5linux`](https://github.com/lucas-campagna/mt5linux) RPyC bridge — so
the main bot can run PAPER/DEMO/LIVE trading from a plain Linux host with
**zero Wine installed on that host**. Wine lives only in this one
container.

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
┌──────────────────────┐        mt5linux (RPyC)        ┌──────────────────────────┐
│  m5-bot container    │ ─────────────────────────────▶│  mt5-bridge container    │
│  (plain Linux)       │        tcp/8001               │  Xvfb + Wine + MT5       │
│  MT5_BRIDGE_MODE=    │                               │  terminal + wine-python  │
│    mt5linux          │                               │  + mt5linux RPyC server  │
└──────────────────────┘                               └──────────────────────────┘
```

- **Xvfb** gives Wine a virtual display — MT5's terminal is a GUI app
  even when driven purely through its API, so it needs *some* display
  target to run against, even headlessly.
- **Wine** hosts an actual MT5 terminal install plus a Windows Python
  install carrying `MetaTrader5`, `rpyc` and `plumbum`.
- **mt5linux** runs an RPyC server exposing the same function calls
  (`initialize()`, `login()`, `copy_rates_from_pos()`, `order_send()`, …)
  over the network. The app's `data/mt5_feed.py` /
  `execution/mt5_adapter.py` call these transparently — same code path as
  a local `MetaTrader5` install, just proxied.
- Login happens purely through those API calls — **nothing here scripts a
  GUI click**. Credentials go in via the dashboard's Broker Connection
  panel.

### Build vs. first boot

The split matters, and it's the main reason this image is more reliable
than the obvious version:

| Happens at **build** time | Happens at **first boot** (into the persisted volume) |
|---|---|
| Alpine + Wine packages | `wineboot --init` (failure tolerated) |
| Windows Python install under Wine | MT5 terminal download + install |
| `MetaTrader5` / `rpyc` / `plumbum` pip install | Terminal config tuning |
| Linux-side `mt5linux` | Starting the terminal + RPyC server |

Anything that talks to the network at length or drives a Windows
installer is deferred to runtime, where a failure is a retryable
`docker compose restart` against a volume that remembers what already
succeeded — rather than a dead image and a 20-minute rebuild. This is
what fixes the `wineboot --init` "boot event wait timed out" /
`could not load kernel32.dll` build failure on small hosts.

### Where this came from

Structure and most of the size/robustness wins are adapted from
[`lucas-campagna/mt5linux@docker-image-optimization`](https://github.com/lucas-campagna/mt5linux/tree/docker-image-optimization/docker):
Alpine instead of Debian+WineHQ, no i386 architecture, the 32-bit Wine
tree deleted, a multi-stage build, `WINEDLLOVERRIDES=mscoree=` to
suppress Wine's Mono prompt, stopping unneeded Wine services after boot,
and the build-time/runtime split above.

Two things from that branch are deliberately **not** copied, because they
don't work:

1. Its RPyC launch is `wine python.exe -m mt5linux` with no arguments.
   `mt5linux` is a *Linux-side* launcher whose first positional argument
   (the Windows python path) is required, and it needs `--host`/`-p` to
   bind anywhere reachable. As written it exits on an argparse error and
   its own watchdog restarts it forever. Ours runs from Linux `python3`
   with the positional supplied and binds `0.0.0.0`.
2. It pip-installs `mt5linux` into the Wine-side Python. Nothing needs it
   there — the generated server only imports `rpyc` and `plumbum` — and
   `mt5linux`'s dependency metadata pins `numpy==1.21.4`, which has no
   wheel for Python 3.11 and would fail that step anyway.

It also hard-codes `wine64`, which newer Wine merged back into `wine`;
ours resolves whichever exists.

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

## Configuration

| Variable | Where | Default | Purpose |
|---|---|---|---|
| `MT5_SETUP_URL` | runtime env | MetaQuotes' generic installer | Your broker's own MT5 installer, if they provide one. Read on **first boot** — to change it after the fact, remove the `mt5-wine-prefix` volume and restart. |
| `MT5LINUX_PORT` | runtime env | `8001` | RPyC listen port; must match `MT5_BRIDGE_PORT`. |
| `WINEDEBUG` | runtime env | `-all` | Set to `fixme-all` temporarily when debugging Wine itself. |
| `WINE_PYTHON_URL` | build arg | Python 3.11.9 (64-bit) | The Python installed *inside* Wine. |

## Troubleshooting

Start with `docker compose logs -f mt5-bridge` — the entrypoint logs each
phase with a `[mt5-bridge]` prefix.

- **First boot is slow.** It downloads and installs the MT5 terminal
  inside Wine. Subsequent starts skip it (persisted in the
  `mt5-wine-prefix` volume).
- **"the installer ran but terminal64.exe never appeared."** Most brokers
  ship a branded installer and the generic MetaQuotes one won't produce a
  usable terminal for them. Set `MT5_SETUP_URL` to your broker's, remove
  the volume (`docker compose down && docker volume rm docker_mt5-wine-prefix`),
  and restart.
- **App reports "connection failed" from the Broker Connection panel.**
  Check this container's logs first — usually either the terminal hasn't
  finished starting or the login/password/server is wrong.
  `MT5_BRIDGE_HOST` must be `mt5-bridge` (the compose service name), not
  `127.0.0.1`, which would point the app container at itself.
- **Wine crashes / the bridge stops responding.** The entrypoint's
  watchdog restarts both the RPyC server and the terminal automatically;
  `docker compose restart mt5-bridge` if it's wedged harder than that.
- **Out of memory on a 1GB host.** See "Running the mt5linux bridge on a
  1GB host" in [`docs/DEPLOYMENT.md`](../../docs/DEPLOYMENT.md).
  `./setup.sh` provisions swap and builds sequentially for this case.

## Honest limitations

- This has **not** been end-to-end verified against a live broker
  connection in this repository — there's no Docker daemon available in
  the environment it was written in, let alone a broker account. Treat
  first boot as a real install against your specific broker.
- **Alpine/musl + Wine is a less-trodden path** than Debian/glibc for MT5
  specifically, and MT5-under-Wine is finicky in general (see the
  [MQL5 forum](https://www.mql5.com/en/forum/371932) threads on Wine
  version regressions). If musl turns out to be the problem, the fallback
  is a Debian base with the same build/runtime split — the structure here
  is what matters, not the distro.
- Wine running a GUI Windows app in a container is inherently more
  fragile than a real Windows VPS or a paid cloud MT5 bridge (e.g.
  MetaApi). Expect to re-verify after MT5 terminal updates.
- If anything drifts from how `mt5linux` currently works, check
  https://github.com/lucas-campagna/mt5linux directly — that project is
  the source of truth for the bridge protocol, not this repo.

If this ends up being more maintenance than it's worth, a small Windows
VPS (`bridge_mode=local`) is the simpler, more reliable fallback — see
the root [`docs/DEPLOYMENT.md`](../../docs/DEPLOYMENT.md).
