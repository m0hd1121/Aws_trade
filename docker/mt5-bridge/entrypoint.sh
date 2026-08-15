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

# One-time environment report. Cheap, and it turns the next Wine problem
# into something diagnosable from the log alone rather than another
# round-trip: "Bad EXE format" on a 64-bit binary, for instance, is a
# 64-bit-support question, which these three lines answer directly.
log "wine binary: ${WINE_BIN} ($("${WINE_BIN}" --version 2>/dev/null || echo 'version unknown'))"
if [ -d /usr/lib/wine/x86_64-windows ]; then
    log "wine 64-bit support: present (/usr/lib/wine/x86_64-windows)"
else
    log "wine 64-bit support: MISSING — 64-bit .exe files will not run"
fi
log "wineprefix: ${WINEPREFIX} (WINEARCH=${WINEARCH:-unset})"

# The container's own memory ceiling, which is enforced independently of
# how much RAM the host has — a too-low limit here SIGKILLs the MT5
# installer even on a large machine, and that is otherwise invisible.
container_mem_limit() {
    if [ -r /sys/fs/cgroup/memory.max ]; then
        cat /sys/fs/cgroup/memory.max                       # cgroup v2
    elif [ -r /sys/fs/cgroup/memory/memory.limit_in_bytes ]; then
        cat /sys/fs/cgroup/memory/memory.limit_in_bytes     # cgroup v1
    else
        echo unknown
    fi
}
MEM_MAX="$(container_mem_limit)"
# "Unlimited" is reported inconsistently: cgroup v2 may say "max", while v1
# (and some v2 setups) report a sentinel so large it renders as millions of
# MB. Treat anything above 1TiB as no limit rather than printing nonsense.
case "${MEM_MAX}" in
    ''|*[!0-9]*) MEM_MAX_DESC="unlimited/unknown"; MEM_MAX="" ;;
    *) if [ "${MEM_MAX}" -gt 1099511627776 ]; then
           MEM_MAX_DESC="unlimited"; MEM_MAX=""
       else
           MEM_MAX_DESC="$((MEM_MAX / 1024 / 1024))MB"
       fi ;;
esac
log "container memory limit: ${MEM_MAX_DESC}"

# --- virtual display -------------------------------------------------
# Prefer xdpyinfo (a real connection attempt), fall back to the X socket
# Xvfb creates when it binds — so this does not hard-depend on one more
# package being present under its expected name.
display_ready() {
    if command -v xdpyinfo >/dev/null 2>&1; then
        xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1
    else
        num="${DISPLAY#:}"
        [ -S "/tmp/.X11-unix/X${num%%.*}" ]
    fi
}

rm -f /tmp/.X99-lock /tmp/.X0-lock
Xvfb "${DISPLAY}" -screen 0 1024x768x16 -nolisten tcp >/dev/null 2>&1 &
XVFB_PID=$!
for _ in $(seq 1 30); do
    display_ready && break
    sleep 1
done
if ! display_ready; then
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
# "The file exists" is NOT the same as "the install finished". The
# installer forks and keeps writing after its launcher returns, so if the
# container dies mid-install (which it did, repeatedly, while earlier bugs
# were crash-looping it) a TRUNCATED terminal64.exe is left behind in the
# persisted volume. Every later boot then reports "already installed" and
# reuses a corrupt binary, which Wine rejects with
#   ShellExecuteEx failed: Bad EXE format
# forever, immune to rebuilding the image. So validate the file, don't
# just look for it: real PE executables start with "MZ", and a genuine
# terminal64.exe is tens of MB.
MIN_TERMINAL_BYTES=5000000

terminal_is_valid() {
    f="$1"
    [ -n "${f}" ] && [ -f "${f}" ] || return 1
    size="$(wc -c < "${f}" 2>/dev/null || echo 0)"
    [ "${size}" -ge "${MIN_TERMINAL_BYTES}" ] || {
        log "terminal64.exe is only ${size} bytes — truncated, not a real install"
        return 1
    }
    magic="$(head -c 2 "${f}" 2>/dev/null | od -An -c | tr -d ' \n')"
    [ "${magic}" = "MZ" ] || {
        log "terminal64.exe does not start with the MZ PE signature (got '${magic}')"
        return 1
    }
    return 0
}

find_terminal() {
    for f in $(find "${WINEPREFIX}/drive_c" -maxdepth 4 -name terminal64.exe -type f 2>/dev/null); do
        if terminal_is_valid "${f}"; then
            echo "${f}"
            return 0
        fi
    done
    return 1
}

TERMINAL="$(find_terminal || true)"
if [ -z "${TERMINAL}" ]; then
    log "No valid MT5 terminal in the prefix — installing."
    # Clear any partial install so the installer starts from clean state.
    rm -rf "${WINEPREFIX}/drive_c/Program Files/MetaTrader 5" 2>/dev/null || true
    log "Downloading ${MT5_SETUP_URL}"
    if ! curl -fsSL -o /tmp/mt5setup.exe "${MT5_SETUP_URL}"; then
        log "FATAL: could not download the MT5 installer."
        log "Check MT5_SETUP_URL / network, then restart this container."
        exit 1
    fi
    log "Running the MT5 installer under Wine (this takes a few minutes)..."
    if "${WINE_BIN}" /tmp/mt5setup.exe /auto; then
        :
    else
        rc=$?
        # 137 = 128 + SIGKILL. Nothing in this script sends that, so it is
        # the OOM killer — and the ceiling it enforced is the CONTAINER's
        # cgroup limit, which applies no matter how much RAM the host has.
        # Worth naming explicitly: a bare "Killed" line looks like an MT5
        # fault and sends you debugging Wine instead of memory.
        if [ "${rc}" -eq 137 ]; then
            log "FATAL: the installer was SIGKILLed by the out-of-memory killer."
            log "This is a memory ceiling, not an MT5 or Wine fault."
            if [ -z "${MEM_MAX}" ]; then
                log "  container limit: ${MEM_MAX_DESC} — so the HOST ran out of RAM."
            else
                log "  container limit: ${MEM_MAX_DESC} (mem_limit in docker-compose.mt5-bridge.yml)"
            fi
            log "  The MT5 installer peaks well above the bridge's steady-state use,"
            log "  so the limit that is right for running it is too small to install it."
            log "  Fix: make sure the host has swap, then retry —"
            log "    sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile \\"
            log "      && sudo mkswap /swapfile && sudo swapon /swapfile"
            log "  Stopping the m5-bot container during the install also frees ~320MB."
            exit 1
        fi
        log "installer returned ${rc}; checking anyway"
    fi

    # Wait for the installer to actually FINISH, not merely for the file to
    # show up: wineserver -w blocks until every Wine process has exited,
    # which is the real completion signal for a forking installer.
    log "Waiting for the installer to finish writing..."
    wineserver -w 2>/dev/null || true

    # Then poll for a file that passes validation, not just one that exists.
    for _ in $(seq 1 60); do
        TERMINAL="$(find_terminal || true)"
        [ -n "${TERMINAL}" ] && break
        sleep 5
    done
    rm -f /tmp/mt5setup.exe
    if [ -z "${TERMINAL}" ]; then
        log "FATAL: the installer ran but produced no valid terminal64.exe."
        log "If the messages above mention a truncated file, the install was"
        log "interrupted — just restart this container and it will retry."
        log "Otherwise your broker likely requires their own branded"
        log "installer: set MT5_SETUP_URL to it and restart."
        log "See docker/mt5-bridge/README.md."
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
# `wine app.exe` is a LAUNCHER: it hands the process off to wineserver and
# can exit long before the Windows app does. So the PID it returns is not
# a liveness signal — checking it with `kill -0` reports a perfectly
# healthy terminal as dead. Ask the process table about terminal64.exe
# instead. (procps is installed for exactly this.)
MT5_LOG=/tmp/mt5-terminal.log

mt5_running() {
    pgrep -f 'terminal64\.exe' >/dev/null 2>&1
}

start_mt5() {
    # Output goes to a file rather than /dev/null so a genuine crash leaves
    # evidence — WINEDEBUG=-all already keeps this quiet in normal operation.
    "${WINE_BIN}" "${TERMINAL}" /portable >"${MT5_LOG}" 2>&1 &
}

log "Starting MT5 terminal..."
start_mt5
for _ in $(seq 1 20); do
    mt5_running && break
    sleep 1
done
if mt5_running; then
    log "MT5 terminal is running (pid $(pgrep -f 'terminal64\.exe' | head -1))"
else
    log "WARNING: terminal64.exe is not in the process table yet."
    log "Last output from it:"
    tail -n 20 "${MT5_LOG}" 2>/dev/null | sed 's/^/    /' || true
    log "Continuing anyway — MetaTrader5.initialize() starts the terminal"
    log "on demand too, so the bridge may still work."
fi

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
    kill "${BRIDGE_PID}" "${XVFB_PID}" 2>/dev/null || true
    pkill -f 'terminal64\.exe' 2>/dev/null || true
    wineserver -k 2>/dev/null || true
    rm -f /tmp/.X99-lock
}
trap cleanup EXIT INT TERM

log "Bridge up. Point the app at MT5_BRIDGE_HOST=mt5-bridge MT5_BRIDGE_PORT=${MT5LINUX_PORT}"
log "Enter broker credentials from the dashboard's Broker Connection panel."

# --- supervise, in the foreground -------------------------------------
# This deliberately does NOT `wait` on ${BRIDGE_PID}: the supervisor below
# replaces that PID on every restart, so waiting on the original would
# both watch a stale PID and — under `set -e` — kill the whole container
# the first time the RPyC server exited non-zero, before any restart could
# happen. That turned a one-line Python ImportError into an endless
# container crash-loop.
#
# A transient death is restarted in place. A persistent one still has to
# surface rather than be papered over, so after MAX_BRIDGE_FAILS quick
# failures we exit non-zero and let Docker's restart policy handle it —
# with the reason visible in the logs.
MAX_BRIDGE_FAILS=5
BRIDGE_FAILS=0
MAX_MT5_FAILS=5
MT5_FAILS=0

while true; do
    sleep 10

    if ! kill -0 "${BRIDGE_PID}" 2>/dev/null; then
        BRIDGE_FAILS=$((BRIDGE_FAILS + 1))
        if [ "${BRIDGE_FAILS}" -ge "${MAX_BRIDGE_FAILS}" ]; then
            log "FATAL: the RPyC server has died ${BRIDGE_FAILS} times in a row."
            log "This is a persistent fault, not a blip — read the traceback above."
            exit 1
        fi
        log "RPyC server died (${BRIDGE_FAILS}/${MAX_BRIDGE_FAILS}) — restarting"
        start_bridge
    else
        # Survived a full interval: treat earlier deaths as transient.
        BRIDGE_FAILS=0
    fi

    # Liveness by process table, not by the wine launcher's PID — see the
    # comment at start_mt5. Capped too: an MT5 that cannot stay up should
    # be reported, not respawned forever on a host with 1GB of RAM.
    if mt5_running; then
        MT5_FAILS=0
    else
        MT5_FAILS=$((MT5_FAILS + 1))
        if [ "${MT5_FAILS}" -ge "${MAX_MT5_FAILS}" ]; then
            log "FATAL: the MT5 terminal has failed to stay up ${MT5_FAILS} times."
            log "Last output from it:"
            tail -n 30 "${MT5_LOG}" 2>/dev/null | sed 's/^/    /' || true
            exit 1
        fi
        log "MT5 terminal not running (${MT5_FAILS}/${MAX_MT5_FAILS}) — restarting"
        start_mt5
    fi
done
