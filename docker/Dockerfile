# Linux image: API + dashboard + BACKTEST/PAPER-analysis workloads.
# DEMO/LIVE trading needs the MetaTrader5 python package, which only ships
# Windows wheels — run those modes on a Windows host (bare metal, VM, or
# Windows container). See docs/DEPLOYMENT.md.

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
