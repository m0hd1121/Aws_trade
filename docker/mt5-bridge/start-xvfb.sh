#!/bin/sh
# Start Xvfb on $DISPLAY (default :99) if it isn't already running, and
# block until it is actually accepting connections (via xdpyinfo) instead
# of guessing with a fixed `sleep N` — the blind-sleep version is what let
# wineboot/wine race an Xvfb that wasn't listening yet on slower hosts.
set -e

DISPLAY_NUM="${DISPLAY:-:99}"

if ! xdpyinfo -display "${DISPLAY_NUM}" >/dev/null 2>&1; then
    Xvfb "${DISPLAY_NUM}" -screen 0 1024x768x16 &
    for i in $(seq 1 30); do
        if xdpyinfo -display "${DISPLAY_NUM}" >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
fi

xdpyinfo -display "${DISPLAY_NUM}" >/dev/null 2>&1 || {
    echo "start-xvfb.sh: Xvfb on ${DISPLAY_NUM} never became ready" >&2
    exit 1
}
