# Alpine + Wine + MetaTrader 5 + the mt5linux RPyC bridge, in one small
# container — lets the main app run on a plain Linux host with zero Wine
# installed there, while this container owns the only Wine instance.
#
# Structure and most of the size/robustness wins here are adapted from
# lucas-campagna/mt5linux's `docker-image-optimization` branch:
#   https://github.com/lucas-campagna/mt5linux/tree/docker-image-optimization/docker
# Specifically: Alpine instead of Debian+WineHQ, a multi-stage build so
# none of the build tooling lands in the runtime image,
# WINEDLLOVERRIDES=mscoree= to
# suppress Wine's Mono prompt, and — the important one — moving Wine
# prefix init and the MT5 install OUT of the build and into runtime, where
# failure is tolerated and retried instead of killing the whole build.
#
# Two things from that branch are deliberately NOT copied, because they're
# broken (see entrypoint.sh for the corrected versions):
#   1. Its `wine python.exe -m mt5linux` call omits mt5linux's REQUIRED
#      positional argument (the Windows python path) and never passes
#      --host/-p, so the server would die on an argparse error and the
#      watchdog would restart it forever. mt5linux is a *Linux*-side
#      launcher that shells out to `wine <win-python> server.py`.
#   2. It pip-installs mt5linux into the Wine-side Python. Nothing needs
#      it there — the generated server only imports rpyc + plumbum — and
#      mt5linux's own dependency metadata pins numpy==1.21.4, which has no
#      wheel for Python 3.11 and would fail the build anyway.
#
# HONESTY NOTE: this has NOT been end-to-end verified against a live
# broker in this repo — there's no Docker daemon available here to build
# it, let alone a broker account to point it at. Alpine/musl + Wine is
# also a less-trodden path than Debian/glibc for MT5 specifically. Treat
# first boot as a real install. See docs/DEPLOYMENT.md.

# ---------------------------------------------------------------------
# Builder: install the Wine-side Windows Python and its packages once,
# then hand the finished prefix to the runtime stage. Everything used to
# get there (curl, pip, build tooling) is left behind in this stage.
# ---------------------------------------------------------------------
FROM alpine:3.20 AS builder

ENV WINEPREFIX=/opt/wineprefix \
    WINEARCH=win64 \
    WINEDEBUG=-all \
    WINEDLLOVERRIDES="mscoree=" \
    DISPLAY=:99

RUN apk add --no-cache wine xvfb curl xdpyinfo

# Windows-side Python. Only three packages ever run under Wine:
#   MetaTrader5 — the real broker API
#   rpyc + plumbum — imported by the server script mt5linux generates
# mt5linux itself stays on the Linux side (see note above).
ARG WINE_PYTHON_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe

# The installer needs a Windows-style TargetDir, but every *invocation*
# below uses the Unix path instead — Wine accepts both, and this avoids
# backslashes surviving two layers of Dockerfile + shell escaping, which
# is a silent-breakage classic.
ENV WINE_PYTHON=/opt/wineprefix/drive_c/Python311/python.exe

COPY with-xvfb.sh /usr/local/bin/with-xvfb.sh
RUN chmod +x /usr/local/bin/with-xvfb.sh

RUN curl -fsSL -o /tmp/python-installer.exe "${WINE_PYTHON_URL}" && \
    with-xvfb.sh wine /tmp/python-installer.exe \
        /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 \
        TargetDir=C:\\Python311 && \
    sleep 5 && \
    wineserver -w && \
    rm -f /tmp/python-installer.exe && \
    test -f "${WINE_PYTHON}"

# rpyc is PINNED, and pinned to the SAME version as the Linux side of the
# bridge (see the runtime stage below). RPyC is a wire protocol spoken
# between the two: letting one side float to whatever is current while the
# other is pinned invites protocol/serialization mismatches that surface
# as obscure errors at connect time rather than as an honest version
# complaint. If you bump one, bump both.
ARG RPYC_VERSION=5.3.1
RUN with-xvfb.sh wine "${WINE_PYTHON}" -m pip install \
        --no-cache-dir --upgrade pip && \
    with-xvfb.sh wine "${WINE_PYTHON}" -m pip install \
        --no-cache-dir MetaTrader5 "rpyc==${RPYC_VERSION}" plumbum && \
    wineserver -w

# ---------------------------------------------------------------------
# Runtime: Alpine + Wine + a Linux python to drive mt5linux. No compiler,
# no build deps.
# ---------------------------------------------------------------------
FROM alpine:3.20

RUN apk add --no-cache \
        wine \
        xvfb \
        xdpyinfo \
        python3 \
        py3-pip \
        curl \
        procps

# NOTE: an earlier version deleted /usr/lib/wine/i386-windows and
# /usr/lib/wine/i386-unix here, copying a size optimization from upstream
# (which drops only i386-windows). Dropped, for two reasons:
#
#   1. It optimizes the wrong resource. Those files cost DISK, not RAM,
#      and RAM is the binding constraint on a small VPS — so the saving
#      bought nothing against the actual limit while adding risk.
#   2. Deleting paths that may not exist under these names on Alpine is a
#      silent no-op that looks like it did something, which makes it a
#      misleading suspect when Wine later misbehaves.
#
# Not reintroducing it without a real build to test against.

# numpy is NOT optional despite --no-deps below: mt5linux/__init__.py does
# `from numpy import array` at module import time, so `python -m mt5linux`
# cannot even start without it. Alpine's own py3-numpy is prebuilt for
# musl, which avoids depending on numpy publishing a musllinux wheel and
# avoids needing a compiler in the image; pip is a fallback if the apk
# package is ever unavailable.
RUN apk add --no-cache py3-numpy || \
    pip install --no-cache-dir --break-system-packages numpy

# Linux-side mt5linux. --no-deps for the same reason as the main image:
# its declared deps pin numpy==1.21.4 (no wheel for modern Python) plus a
# pile of unrelated packaging tools. numpy above and rpyc here are its
# only real runtime needs.
# Keep RPYC_VERSION identical to the builder stage's — see the note there.
# Also promoted to ENV so entrypoint.sh can reconcile the Wine side against
# it at boot: the Wine prefix is a named volume, so the packages installed
# into it at build time are frozen at whatever the volume was first created
# with and are NOT refreshed by rebuilding this image.
ARG RPYC_VERSION=5.3.1
ENV RPYC_VERSION=${RPYC_VERSION}
RUN pip install --no-cache-dir --break-system-packages --no-deps mt5linux==0.1.9 && \
    pip install --no-cache-dir --break-system-packages "rpyc==${RPYC_VERSION}" && \
    python3 -c "import mt5linux"

COPY --from=builder /opt/wineprefix /opt/wineprefix

COPY with-xvfb.sh /usr/local/bin/with-xvfb.sh
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /usr/local/bin/with-xvfb.sh /entrypoint.sh

ENV WINEPREFIX=/opt/wineprefix \
    WINEARCH=win64 \
    WINEDEBUG=-all \
    WINEDLLOVERRIDES="mscoree=" \
    DISPLAY=:99 \
    WINE_PYTHON=/opt/wineprefix/drive_c/Python311/python.exe \
    MT5LINUX_HOST=0.0.0.0 \
    MT5LINUX_PORT=8001 \
    # Point at YOUR broker's own installer if they ship one (most do, to
    # preselect their server list). Downloaded on FIRST BOOT, not at build
    # time, into the persisted wineprefix volume — so a failed install is
    # a retryable container restart, not a broken image.
    MT5_SETUP_URL=https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe

EXPOSE 8001

ENTRYPOINT ["/entrypoint.sh"]
