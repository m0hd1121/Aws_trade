# Alpine + Wine + MetaTrader 5 + the mt5linux RPyC bridge, in one small
# container — lets the main app run on a plain Linux host with zero Wine
# installed there, while this container owns the only Wine instance.
#
# Structure and most of the size/robustness wins here are adapted from
# lucas-campagna/mt5linux's `docker-image-optimization` branch:
#   https://github.com/lucas-campagna/mt5linux/tree/docker-image-optimization/docker
# Specifically: Alpine instead of Debian+WineHQ, no i386 architecture, the
# 32-bit Wine tree deleted outright, a multi-stage build so none of the
# build tooling lands in the runtime image, WINEDLLOVERRIDES=mscoree= to
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
    WINEDEBUG=-all \
    WINEDLLOVERRIDES="mscoree=" \
    DISPLAY=:99

RUN apk add --no-cache wine xvfb curl x11-utils

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

RUN with-xvfb.sh wine "${WINE_PYTHON}" -m pip install \
        --no-cache-dir --upgrade pip && \
    with-xvfb.sh wine "${WINE_PYTHON}" -m pip install \
        --no-cache-dir MetaTrader5 rpyc plumbum && \
    wineserver -w

# ---------------------------------------------------------------------
# Runtime: Alpine + Wine + a Linux python to drive mt5linux. No compiler,
# no curl-time build deps, no 32-bit Wine.
# ---------------------------------------------------------------------
FROM alpine:3.20

RUN apk add --no-cache \
        wine \
        xvfb \
        x11-utils \
        python3 \
        py3-pip \
        curl \
        procps \
    # MT5's terminal64.exe is 64-bit; the 32-bit Wine tree is dead weight
    # (~hundreds of MB) in an image that will never load a 32-bit PE.
    && rm -rf /usr/lib/wine/i386-windows /usr/lib/wine/i386-unix

# Linux-side mt5linux. --no-deps for the same reason as the main image:
# its declared deps pin numpy==1.21.4 plus a pile of unrelated packaging
# tools. rpyc is its only real runtime need here.
RUN pip install --no-cache-dir --break-system-packages --no-deps mt5linux==0.1.9 && \
    pip install --no-cache-dir --break-system-packages rpyc==5.3.1

COPY --from=builder /opt/wineprefix /opt/wineprefix

COPY with-xvfb.sh /usr/local/bin/with-xvfb.sh
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /usr/local/bin/with-xvfb.sh /entrypoint.sh

ENV WINEPREFIX=/opt/wineprefix \
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
