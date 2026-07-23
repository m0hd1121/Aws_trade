#!/bin/bash
# Starts the virtual display Wine/MT5 need to run at all, then the
# mt5linux RPyC server (which runs under Wine's python and imports the
# real MetaTrader5 package). The MT5 terminal itself is started
# on-demand by MetaTrader5.initialize() the first time a client connects
# — exactly the same lazy-start behavior as on native Windows.
set -e

Xvfb :99 -screen 0 1024x768x16 &
XVFB_PID=$!

cleanup() {
  kill "$XVFB_PID" 2>/dev/null || true
}
trap cleanup EXIT

for i in $(seq 1 30); do
  xdpyinfo -display :99 >/dev/null 2>&1 && break
  sleep 1
done
xdpyinfo -display :99 >/dev/null 2>&1 || {
  echo "entrypoint.sh: Xvfb on :99 never became ready" >&2
  exit 1
}

echo "Starting mt5linux bridge server on 0.0.0.0:${MT5LINUX_PORT:-8001} ..."
exec wine python -m mt5linux --host 0.0.0.0 -p "${MT5LINUX_PORT:-8001}" wine python
