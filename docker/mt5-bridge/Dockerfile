# Alpine + Wine + MetaTrader 5 + the mt5linux RPyC bridge, in one small
# container — lets the main app run on a plain Linux host with zero Wine
# installed there, while this container owns the only Wine instance.
#
# Structure and most of the robustness wins here are adapted from
# lucas-campagna/mt5linux's `docker-image-optimization` branch:
#   https://github.com/lucas-campagna/mt5linux/tree/docker-image-optimization/docker
# A multi-stage build so none of the build tooling lands in the runtime
# image, WINEDLLOVERRIDES=mscoree= to suppress Wine's Mono prompt, and —
# the important one — moving Wine prefix init and the MT5 install OUT of
# the build and into runtime, where failure is tolerated and retried
# instead of killing the whole build.
#
# BASE IMAGE: Debian, NOT Alpine. That branch uses Alpine, and this file
# did too for a while — it builds fine and is much smaller. But on
# Alpine's musl-based Wine, `import MetaTrader5` HANGS FOREVER inside the
# Wine-side Python: no CPU burned, never returns, verified with a 180s
# standalone timeout. Everything else worked there (Wine 9.0 64-bit, the
# MT5 install, the RPyC transport, `import rpyc` in the same interpreter
# returning in under a second) — it is specifically that compiled .pyd
# failing to load under musl. Debian/glibc is the well-trodden path for
# MT5 under Wine. Do not "optimize" this back to Alpine without actually
# testing that import.
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
# it, let alone a broker account to point it at. Treat first boot as a
# real install. See docs/DEPLOYMENT.md.
#
# WINE VERSION IS PINNED, on purpose, to 9.0.0.0~bookworm-1 — do not let it
# float to whatever `winehq-stable` currently resolves to. Confirmed by
# direct observation: the generic MetaQuotes mt5setup.exe's own anti-tamper
# check pops "A debugger has been found running in your system" under Wine
# 11.0 and refuses to proceed — dismissing the dialog makes the installer
# exit (code 222) with nothing written, not continue. The SAME installer
# completed cleanly under Wine 9.0 on an earlier build of this image. That
# strongly suggests something Wine changed between 9.0 and 11.0 (plausibly
# more complete NT debug-API emulation) now trips a check 9.0 silently
# didn't implement accurately enough to trigger. If you ever bump this,
# retest the actual install against a real installer, headless — a build
# that completes is not enough evidence; this exact failure mode builds
# fine and only surfaces at runtime.

# ---------------------------------------------------------------------
# Builder: install the Wine-side Windows Python and its packages once,
# then hand the finished prefix to the runtime stage. Everything used to
# get there (curl, pip, build tooling) is left behind in this stage.
# ---------------------------------------------------------------------
FROM debian:bookworm-slim AS builder
ARG WINE_VERSION=9.0.0.0~bookworm-1

ENV DEBIAN_FRONTEND=noninteractive \
    WINEPREFIX=/opt/wineprefix \
    WINEARCH=win64 \
    WINEDEBUG=-all \
    WINEDLLOVERRIDES="mscoree=" \
    DISPLAY=:99

# WineHQ's own packages rather than Debian's older bundled ones. i386 is
# added because winehq-stable depends on it; the 32-bit tree is left in
# place (see the note in the runtime stage about not deleting it). All
# four wine packages are pinned to the SAME version in one apt-get
# transaction — pinning only winehq-stable would still let apt satisfy its
# unversioned dependency on wine-stable with whatever is newest.
RUN dpkg --add-architecture i386 && \
    apt-get update && apt-get install -y --no-install-recommends \
        wget gnupg2 ca-certificates curl xvfb x11-utils winbind \
    && mkdir -pm755 /etc/apt/keyrings \
    && wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key \
    && wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/debian/dists/bookworm/winehq-bookworm.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        "winehq-stable=${WINE_VERSION}" \
        "wine-stable=${WINE_VERSION}" \
        "wine-stable-amd64=${WINE_VERSION}" \
        "wine-stable-i386=${WINE_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

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
# Runtime: Debian + Wine + a Linux python to drive mt5linux. No compiler,
# no build deps.
# ---------------------------------------------------------------------
FROM debian:bookworm-slim
ARG WINE_VERSION=9.0.0.0~bookworm-1

ENV DEBIAN_FRONTEND=noninteractive

# xdpyinfo lives in x11-utils on Debian (on Alpine it is its own package —
# a difference that broke an earlier build). procps provides pgrep, used to
# check whether terminal64.exe is actually running. WINE_VERSION pin: see
# the note at the top of this file — not cosmetic, the generic installer
# will not complete under a newer Wine.
RUN dpkg --add-architecture i386 && \
    apt-get update && apt-get install -y --no-install-recommends \
        wget gnupg2 ca-certificates curl xvfb x11-utils winbind procps \
        python3 python3-pip python3-numpy \
    && mkdir -pm755 /etc/apt/keyrings \
    && wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key \
    && wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/debian/dists/bookworm/winehq-bookworm.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        "winehq-stable=${WINE_VERSION}" \
        "wine-stable=${WINE_VERSION}" \
        "wine-stable-amd64=${WINE_VERSION}" \
        "wine-stable-i386=${WINE_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

# NOTE: an earlier version deleted /usr/lib/wine/i386-windows and
# /usr/lib/wine/i386-unix here, copying a size optimization from upstream
# (which drops only i386-windows). Do not reintroduce it. It optimizes the
# wrong resource — those files cost DISK, not RAM, and RAM is the binding
# constraint on a small VPS — so it buys nothing against the actual limit
# while risking Wine's loader in ways that are tedious to diagnose.

# numpy is NOT optional despite --no-deps below: mt5linux/__init__.py does
# `from numpy import array` at module import time, so `python -m mt5linux`
# cannot even start without it. Installed as python3-numpy in the apt line
# above — distro-packaged, so no wheel availability or compiler needed.

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
