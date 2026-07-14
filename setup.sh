#!/usr/bin/env bash
# One-command setup: brings up the bot + dashboard on a plain Linux host,
# with the all-Linux mt5linux Wine bridge by default (no Wine on this
# host itself). Credentials are entered afterward from the dashboard's
# Broker Connection panel — nothing here needs your MT5 login to run.
#
# Usage:
#   ./setup.sh                 # app + mt5linux Wine bridge (default)
#   ./setup.sh --no-bridge      # app only — for BACKTEST/dashboard use,
#                               #   or if you already run MT5 elsewhere
#                               #   (bridge_mode=local, a Windows VPS, etc.)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

WITH_BRIDGE=1
for arg in "$@"; do
  case "$arg" in
    --no-bridge) WITH_BRIDGE=0 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
  esac
done

if ! command -v docker &> /dev/null; then
  echo "Docker is required but not found. Install it first: https://docs.docker.com/engine/install/" >&2
  exit 1
fi
if ! docker compose version &> /dev/null; then
  echo "The 'docker compose' plugin is required (docker-compose v2+)." >&2
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example."
fi

# These three must match the docker-compose service topology (the bridge
# container is reachable as host "mt5-bridge" on the compose network) —
# force them rather than "only if missing," since a stale placeholder
# value (e.g. 127.0.0.1 from .env.example) would otherwise point the app
# container at itself instead of the bridge container.
set_env() {
  local key="$1" value="$2"
  if grep -q "^${key}=" .env; then
    sed -i.bak "s/^${key}=.*/${key}=${value}/" .env && rm -f .env.bak
  else
    echo "${key}=${value}" >> .env
  fi
}

if [ "$WITH_BRIDGE" -eq 1 ]; then
  set_env MT5_BRIDGE_MODE mt5linux
  set_env MT5_BRIDGE_HOST mt5-bridge
  set_env MT5_BRIDGE_PORT 8001
fi

COMPOSE_FILES=(-f docker/docker-compose.yml)
if [ "$WITH_BRIDGE" -eq 1 ]; then
  COMPOSE_FILES+=(-f docker/docker-compose.mt5-bridge.yml)
  echo "Building app + Wine/MT5 bridge. First build of the bridge image is slow"
  echo "(installs Wine + MT5 terminal + Python inside it — often 15-30+ minutes)."
else
  echo "Building app only (--no-bridge: BACKTEST/dashboard, or MT5 reached some other way)."
fi

docker compose "${COMPOSE_FILES[@]}" up -d --build

echo
echo -n "Waiting for the app to become healthy"
for _ in $(seq 1 60); do
  if curl -sf http://localhost:8000/api/healthz > /dev/null 2>&1; then
    echo " — up."
    break
  fi
  echo -n "."
  sleep 2
done

cat <<EOF

======================================================================
 Dashboard: http://localhost:8000

 Next steps:
   1. Open the dashboard.
   2. Use the Broker Connection panel to enter your MT5 login/password/
      server (this talks to the API directly — no GUI/VNC step).
   3. Click Start Bot once connected.

 Bridge container logs (if built): docker compose ${COMPOSE_FILES[*]} logs -f mt5-bridge
 Stop everything:                  docker compose ${COMPOSE_FILES[*]} down
======================================================================
EOF
