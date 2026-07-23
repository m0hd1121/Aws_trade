# Wine + MetaTrader 5 terminal + the mt5linux RPyC bridge, in one
# container — lets the main app run on a plain Linux host with zero Wine
# installed there, while this container owns the only Wine instance.
#
# HONESTY NOTE: this follows the well-documented community pattern for
# running MT5-under-Wine headlessly (Xvfb for a virtual display, WineHQ's
# own Debian packages, mt5linux as the RPyC bridge) — the same approach
# used by community images like gmag11/MetaTrader5-docker-image. It has
# NOT been end-to-end verified against a live broker connection in this
# repository's own CI (there's no Windows/Wine available to test against
# here). Treat first boot as a real install: expect to iterate on it
# against YOUR broker's terminal build, and cross-check against
# https://github.com/lucas-campagna/mt5linux if anything here drifts from
# how that project currently works. See docs/DEPLOYMENT.md for the honest
# tradeoffs of this path vs. a plain Windows VPS.

FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    WINEARCH=win64 \
    WINEPREFIX=/root/.wine \
    WINEDEBUG=fixme-all \
    DISPLAY=:99

# --- Wine (WineHQ's own packages, not Debian's older bundled ones) ---
# dbus-x11 + x11-utils are here specifically because their absence is a
# common cause of "boot event wait timed out" / "could not load
# kernel32.dll" failures on `wineboot --init` in minimal containers —
# some of Wine's service emulation expects a session bus to exist, and
# xdpyinfo lets the steps below actually confirm Xvfb is accepting
# connections instead of guessing with a fixed sleep.
RUN dpkg --add-architecture i386 && \
    apt-get update && apt-get install -y --no-install-recommends \
        wget gnupg2 ca-certificates xvfb winbind cabextract unzip dbus-x11 x11-utils \
    && mkdir -pm755 /etc/apt/keyrings && \
    wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key && \
    wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/debian/dists/bookworm/winehq-bookworm.sources && \
    apt-get update && apt-get install -y --no-install-recommends winehq-stable && \
    rm -rf /var/lib/apt/lists/*

# winetricks — used to install fonts/runtimes MT5's UI needs to run at all.
RUN wget -O /usr/local/bin/winetricks https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks && \
    chmod +x /usr/local/bin/winetricks

# Shared helper: start Xvfb and actually wait for it to accept connections
# (xdpyinfo) instead of a blind `sleep N`, which is the other half of what
# makes wineboot's internal boot-event handshake flaky on a slow/single-vCPU
# host — if Wine starts talking to a display that isn't ready yet, later
# steps see exactly the "failed to marshal"/"boot event timed out" errors
# from this issue.
COPY start-xvfb.sh /usr/local/bin/start-xvfb.sh
RUN chmod +x /usr/local/bin/start-xvfb.sh

# --- Initialize the Wine prefix (its own layer: if winetricks below fails,
# a retry doesn't have to redo this part too — and wineboot itself gets a
# few attempts, since its boot-event handshake can be flaky under CPU
# contention on a single-vCPU host rather than being a permanent failure). ---
RUN /usr/local/bin/start-xvfb.sh && \
    for attempt in 1 2 3; do \
        wine wineboot --init && break; \
        echo "wineboot --init attempt ${attempt} failed, retrying..." >&2; \
        wineserver -k || true; \
        sleep 5; \
    done && \
    wineserver -w

# --- Fonts + VC++ runtime MT5's UI needs to actually run ---
RUN /usr/local/bin/start-xvfb.sh && \
    winetricks -q corefonts vcrun2019 && \
    wineserver -w

# --- MT5 terminal ---
# Point MT5_SETUP_URL at YOUR broker's own installer if they provide one
# (many require it, to preselect their server list) — the generic
# MetaQuotes installer works for brokers using the shared MT5 network.
ARG MT5_SETUP_URL=https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe
RUN /usr/local/bin/start-xvfb.sh && \
    wget -O /root/mt5setup.exe "${MT5_SETUP_URL}" && \
    wine /root/mt5setup.exe /auto && \
    sleep 20 && \
    wineserver -w && \
    rm -f /root/mt5setup.exe

# --- Wine-side Python + the real MetaTrader5 package + mt5linux server ---
ARG WINE_PYTHON_URL=https://www.python.org/ftp/python/3.9.13/python-3.9.13-amd64.exe
RUN /usr/local/bin/start-xvfb.sh && \
    wget -O /root/python-installer.exe "${WINE_PYTHON_URL}" && \
    wine /root/python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 && \
    sleep 10 && \
    wineserver -w && \
    rm -f /root/python-installer.exe

RUN /usr/local/bin/start-xvfb.sh && \
    wine python -m pip install --no-cache-dir MetaTrader5 mt5linux && \
    wineserver -w

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# The RPyC bridge port the main app's MT5_BRIDGE_HOST/PORT point at.
EXPOSE 8001

ENTRYPOINT ["/entrypoint.sh"]
