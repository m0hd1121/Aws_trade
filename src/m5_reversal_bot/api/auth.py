"""Optional HTTP Basic Auth in front of the whole app — dashboard static
files and every /api/* route, including the WebSocket. Enforced only when
both DASHBOARD_USERNAME and DASHBOARD_PASSWORD are set; otherwise this is
a no-op, matching the existing "put it behind your own VPN/reverse proxy"
guidance in docs/DEPLOYMENT.md.

This is a plain ASGI middleware (not `BaseHTTPMiddleware`) on purpose:
Starlette's `BaseHTTPMiddleware` only sees `http`-scope requests and
silently passes `websocket`-scope connections straight through
unauthenticated, which would leave live trade/account data on `/api/ws`
exposed even with auth "on."
"""

from __future__ import annotations

import base64
import hmac
import logging

from ..core.config import app_settings

log = logging.getLogger("m5_reversal_bot.api.auth")

EXEMPT_PATHS = {"/api/healthz"}


def _auth_configured() -> bool:
    return bool(app_settings.dashboard_username and app_settings.dashboard_password)


def _check_credentials(auth_header: str) -> bool:
    if not auth_header.lower().startswith("basic "):
        return False
    try:
        decoded = base64.b64decode(auth_header.split(" ", 1)[1]).decode("utf-8")
        supplied_user, _, supplied_pass = decoded.partition(":")
    except Exception:
        return False
    return hmac.compare_digest(supplied_user, app_settings.dashboard_username) and hmac.compare_digest(
        supplied_pass, app_settings.dashboard_password
    )


class BasicAuthASGIMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket") or not _auth_configured() or scope.get("path") in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        auth_header = headers.get(b"authorization", b"").decode("latin-1")

        if _check_credentials(auth_header):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            # No HTTP status codes on the WS wire protocol itself — reject
            # before ever sending websocket.accept.
            await receive()
            await send({"type": "websocket.close", "code": 1008})
            return

        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"www-authenticate", b'Basic realm="M5 Reversal Bot"'),
                (b"content-type", b"text/plain"),
            ],
        })
        await send({"type": "http.response.body", "body": b"Authentication required"})


def warn_if_auth_disabled() -> None:
    if not _auth_configured():
        log.warning(
            "DASHBOARD_USERNAME/DASHBOARD_PASSWORD are not set — the dashboard and API "
            "are running with NO authentication. Fine behind your own VPN/reverse proxy; "
            "set both env vars to require HTTP Basic Auth before exposing this more broadly, "
            "especially once real broker credentials are entered via the Broker Connection panel."
        )
