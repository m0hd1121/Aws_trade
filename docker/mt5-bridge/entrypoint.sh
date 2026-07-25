#!/bin/sh
# Bring up the Wine-hosted MT5 terminal and the mt5linux RPyC bridge the
# main app talks to via MT5_BRIDGE_HOST/MT5_BRIDGE_PORT.
#
# Everything fragile happens HERE rather than at image-build time, into
# the persisted /opt/wineprefix volume: the Wine prefix init and the MT5
# terminal install. A failure is then a retryable container restart
# against a volume that remembers what already succeeded, instead of a
# dead image. This is the main structural idea borrowed from
# lucas-campagna/mt5linux's docker-image-optimization branch.
set -e

WINEPREFIX="${WINEPREFIX:-/opt/wineprefix}"
export WINEPREFIX
export WINEDEBUG="${WINEDEBUG:--all}"
export WINEDLLOVERRIDES="${WINEDLLOVERRIDES:-mscoree=}"
export DISPLAY="${DISPLAY:-:99}"

MT5LINUX_HOST="${MT5LINUX_HOST:-0.0.0.0}"
MT5LINUX_PORT="${MT5LINUX_PORT:-8001}"
WINE_PYTHON="${WINE_PYTHON:-/opt/wineprefix/drive_c/Python311/python.exe}"

# Newer Wine merged wine64 into wine; Alpine's package has varied. Resolve
# rather than assume — the upstream branch hard-codes `wine64`, which is
# exactly the kind of thing that breaks on a version bump.
if command -v wine64 >/dev/null 2>&1; then
    WINE_BIN=wine64
else
    WINE_BIN=wine
fi

log() { echo "[mt5-bridge] $*"; }

# --- virtual display -------------------------------------------------
rm -f /tmp/.X99-lock /tmp/.X0-lock
Xvfb "${DISPLAY}" -screen 0 1024x768x16 -nolisten tcp >/dev/null 2>&1 &
XVFB_PID=$!
for _ in $(seq 1 30); do
    xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1 && break
    sleep 1
done
if ! xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; then
    log "FATAL: Xvfb on ${DISPLAY} never became ready"
    exit 1
fi
log "Xvfb ready on ${DISPLAY} (pid ${XVFB_PID})"

# --- Wine prefix -----------------------------------------------------
# Tolerated on purpose. wineboot's boot-event handshake is flaky under CPU
# contention on small hosts, but a prefix that already has a working
# Python in it (baked by the builder stage) does not actually need this to
# succeed — the subsequent `wine` calls will initialize what they need.
log "Initializing Wine prefix (failure tolerated)..."
"${WINE_BIN}" wineboot --init >/dev/null 2>&1 || log "wineboot returned non-zero; continuing"
wineserver -w 2>/dev/null || true

# --- MT5 terminal (first boot only) ----------------------------------
find_terminal() {
    find "${WINEPREFIX}/drive_c" -maxdepth 4 -name terminal64.exe -type f 2>/dev/null | head -1
}

TERMINAL="$(find_terminal)"
if [ -z "${TERMINAL}" ]; then
    log "MT5 terminal not present in the prefix — installing (first boot)."
    log "Downloading ${MT5_SETUP_URL}"
    if ! curl -fsSL -o /tmp/mt5setup.exe "${MT5_SETUP_URL}"; then
        log "FATAL: could not download the MT5 installer."
        log "Check MT5_SETUP_URL / network, then restart this container."
        exit 1
    fi
    log "Running the MT5 installer under Wine (this takes a few minutes)..."
    "${WINE_BIN}" /tmp/mt5setup.exe /auto || log "installer returned non-zero; checking anyway"
    # The installer forks and keeps working after its launcher returns.
    for _ in $(seq 1 60); do
        TERMINAL="$(find_terminal)"
        [ -n "${TERMINAL}" ] && break
        sleep 5
    done
    wineserver -w 2>/dev/null || true
    rm -f /tmp/mt5setup.exe
    if [ -z "${TERMINAL}" ]; then
        log "FATAL: the installer ran but terminal64.exe never appeared."
        log "Most likely your broker requires their own branded installer —"
        log "set MT5_SETUP_URL to it and restart. See docker/mt5-bridge/README.md."
        exit 1
    fi
    log "MT5 installed at ${TERMINAL}"
else
    log "MT5 terminal already installed at ${TERMINAL} (persisted volume)"
fi

# --- trim the terminal's own resource use ----------------------------
# News/signals/market-watch/mail all cost RAM and network in a terminal
# that exists only to serve API calls. Written as UTF-16LE, which is what
# MT5 expects; generated with python3 rather than iconv (busybox's iconv
# is not dependable, and this container already has a Linux python).
write_config() {
    config_dir="$(dirname "${TERMINAL}")/Config"
    mkdir -p "${config_dir}"
    python3 - "$config_dir/common.ini" <<'PYEOF'
import sys
body = """[Common]
NewsEnable=0
SoundEnable=0
MailEnable=0
ProxyEnable=0

[Experts]
Enabled=0

[News]
Enabled=0
AutoUpdate=0

[Signal]
Enabled=0
AutoUpdate=0

[Charts]
MaxBars=50000
"""
open(sys.argv[1], "wb").write(body.encode("utf-16-le"))
PYEOF
    log "Wrote low-resource terminal config to ${config_dir}/common.ini"
}
write_config || log "could not write terminal config; continuing"

# --- MT5 terminal process --------------------------------------------
log "Starting MT5 terminal..."
"${WINE_BIN}" "${TERMINAL}" /portable >/dev/null 2>&1 &
MT5_PID=$!
sleep 10

# --- mt5linux RPyC server --------------------------------------------
# NOTE the argument order. mt5linux is a LINUX-side launcher: it writes an
# rpyc server script, then runs `wine <win-python> that-script --host H -p P`.
# The Windows python path is a REQUIRED POSITIONAL argument. Upstream's
# branch calls `wine python.exe -m mt5linux` with no positional and no
# host/port, which dies on argparse and gets restarted forever by its own
# watchdog. Run it from python3 (Linux) with the positional supplied.
start_bridge() {
    log "Starting mt5linux RPyC server on ${MT5LINUX_HOST}:${MT5LINUX_PORT}"
    python3 -m mt5linux \
        --host "${MT5LINUX_HOST}" \
        -p "${MT5LINUX_PORT}" \
        -w "${WINE_BIN}" \
        "${WINE_PYTHON}" &
    BRIDGE_PID=$!
    log "mt5linux server pid ${BRIDGE_PID}"
}
start_bridge

# --- drop Wine services MT5 doesn't need ------------------------------
# Meaningful on a 1GB host: these are pure overhead for an API-only
# terminal. Deliberately does NOT touch winedevice.exe — MT5's networking
# has been seen to depend on it, and the RAM saved isn't worth the risk.
sleep 5
for proc in explorer.exe plugplay.exe; do
    pid="$(pgrep -f "${proc}" 2>/dev/null | head -1)"
    if [ -n "${pid}" ]; then
        log "Stopping unnecessary Wine process ${proc} (pid ${pid})"
        kill "${pid}" 2>/dev/null || true
    fi
done

cleanup() {
    log "Shutting down..."
    kill "${WATCHDOG_PID}" "${BRIDGE_PID}" "${MT5_PID}" "${XVFB_PID}" 2>/dev/null || true
    wineserver -k 2>/dev/null || true
    rm -f /tmp/.X99-lock
}
trap cleanup EXIT INT TERM

# --- watchdog ---------------------------------------------------------
watchdog() {
    while true; do
        sleep 10
        if ! kill -0 "${BRIDGE_PID}" 2>/dev/null; then
            log "RPyC server (pid ${BRIDGE_PID}) died — restarting"
            start_bridge
        fi
        if ! kill -0 "${MT5_PID}" 2>/dev/null; then
            log "MT5 terminal (pid ${MT5_PID}) died — restarting"
            "${WINE_BIN}" "${TERMINAL}" /portable >/dev/null 2>&1 &
            MT5_PID=$!
        fi
    done
}
watchdog &
WATCHDOG_PID=$!

log "Bridge up. Point the app at MT5_BRIDGE_HOST=mt5-bridge MT5_BRIDGE_PORT=${MT5LINUX_PORT}"
log "Enter broker credentials from the dashboard's Broker Connection panel."

wait "${BRIDGE_PID}"
