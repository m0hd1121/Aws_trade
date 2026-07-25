#!/bin/sh
# Run a command with Xvfb guaranteed to be up and accepting connections.
#
#   with-xvfb.sh wine something.exe /quiet
#
# Waits via xdpyinfo rather than a blind `sleep N` — Wine talking to a
# display that isn't listening yet is what produced the "boot event wait
# timed out" / "could not load kernel32.dll" failures this replaces.
set -e

DISPLAY="${DISPLAY:-:99}"
export DISPLAY

if ! xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; then
    rm -f "/tmp/.X${DISPLAY#:}-lock"
    Xvfb "${DISPLAY}" -screen 0 1024x768x16 -nolisten tcp >/dev/null 2>&1 &
    for _ in $(seq 1 30); do
        xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1 && break
        sleep 1
    done
fi

if ! xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; then
    echo "with-xvfb.sh: Xvfb on ${DISPLAY} never became ready" >&2
    exit 1
fi

exec "$@"
