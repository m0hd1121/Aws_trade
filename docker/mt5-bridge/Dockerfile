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
    DISPLAY=:99

# --- Wine (WineHQ's own packages, not Debian's older bundled ones) ---
RUN dpkg --add-architecture i386 && \
    apt-get update && apt-get install -y --no-install-recommends \
        wget gnupg2 ca-certificates xvfb winbind cabextract unzip \
    && mkdir -pm755 /etc/apt/keyrings && \
    wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key && \
    wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/debian/dists/bookworm/winehq-bookworm.sources && \
    apt-get update && apt-get install -y --no-install-recommends winehq-stable && \
    rm -rf /var/lib/apt/lists/*

# winetricks — used to install fonts/runtimes MT5's UI needs to run at all.
RUN wget -O /usr/local/bin/winetricks https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks && \
    chmod +x /usr/local/bin/winetricks

# --- Initialize the Wine prefix and required runtimes ---
RUN Xvfb :99 -screen 0 1024x768x16 & \
    sleep 4 && \
    wine wineboot --init && \
    winetricks -q corefonts vcrun2019 && \
    wineserver -w

# --- MT5 terminal ---
# Point MT5_SETUP_URL at YOUR broker's own installer if they provide one
# (many require it, to preselect their server list) — the generic
# MetaQuotes installer works for brokers using the shared MT5 network.
ARG MT5_SETUP_URL=https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe
RUN Xvfb :99 -screen 0 1024x768x16 & \
    sleep 4 && \
    wget -O /root/mt5setup.exe "${MT5_SETUP_URL}" && \
    wine /root/mt5setup.exe /auto && \
    sleep 20 && \
    wineserver -w && \
    rm -f /root/mt5setup.exe

# --- Wine-side Python + the real MetaTrader5 package + mt5linux server ---
ARG WINE_PYTHON_URL=https://www.python.org/ftp/python/3.9.13/python-3.9.13-amd64.exe
RUN Xvfb :99 -screen 0 1024x768x16 & \
    sleep 4 && \
    wget -O /root/python-installer.exe "${WINE_PYTHON_URL}" && \
    wine /root/python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 && \
    sleep 10 && \
    wineserver -w && \
    rm -f /root/python-installer.exe

RUN Xvfb :99 -screen 0 1024x768x16 & \
    sleep 4 && \
    wine python -m pip install --no-cache-dir MetaTrader5 mt5linux && \
    wineserver -w

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# The RPyC bridge port the main app's MT5_BRIDGE_HOST/PORT point at.
EXPOSE 8001

ENTRYPOINT ["/entrypoint.sh"]
