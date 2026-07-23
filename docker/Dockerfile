# Linux image: API + dashboard + BACKTEST/PAPER-analysis workloads, and
# PAPER/DEMO/LIVE when paired with the mt5linux bridge (docker-compose.
# mt5-bridge.yml) — otherwise DEMO/LIVE need a Windows host directly, since
# the real MetaTrader5 python package only ships Windows wheels. See
# docs/DEPLOYMENT.md.

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps kept minimal on purpose — no build toolchain, no ML runtime,
# consistent with the "low RAM/CPU" requirement.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# --no-deps: mt5linux's own declared dependencies are broken on modern
# Python (numpy==1.21.4 has no wheel for cp311+) and mostly irrelevant to
# its actual runtime use anyway — see the comment in requirements.txt.
# numpy/rpyc above are its real needs, installed at compatible versions.
RUN pip install --no-cache-dir --no-deps mt5linux==0.1.9

COPY src ./src
COPY config ./config
COPY dashboard ./dashboard
COPY docs ./docs
COPY scripts ./scripts
COPY pyproject.toml .

ENV PYTHONPATH=/app/src
RUN mkdir -p /app/data /app/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/healthz || exit 1

CMD ["uvicorn", "m5_reversal_bot.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
