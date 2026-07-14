"""Verifies the optional dashboard/API Basic Auth: off by default (no
breaking change for existing deployments), and when both
DASHBOARD_USERNAME/PASSWORD are set, blocks HTTP routes, static files,
and the WebSocket alike unless the right credentials are supplied.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from m5_reversal_bot.api.main import app
from m5_reversal_bot.core.config import app_settings


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def with_auth_configured():
    original_user, original_pass = app_settings.dashboard_username, app_settings.dashboard_password
    app_settings.dashboard_username = "admin"
    app_settings.dashboard_password = "s3cret"
    yield
    app_settings.dashboard_username, app_settings.dashboard_password = original_user, original_pass


def test_auth_disabled_by_default(client):
    assert app_settings.dashboard_username == ""
    r = client.get("/api/bot/status")
    assert r.status_code == 200


def test_rejects_missing_credentials_when_configured(client, with_auth_configured):
    r = client.get("/api/bot/status")
    assert r.status_code == 401
    assert "Basic" in r.headers.get("www-authenticate", "")


def test_rejects_wrong_credentials(client, with_auth_configured):
    r = client.get("/api/bot/status", auth=("admin", "wrong"))
    assert r.status_code == 401


def test_accepts_right_credentials(client, with_auth_configured):
    r = client.get("/api/bot/status", auth=("admin", "s3cret"))
    assert r.status_code == 200


def test_healthz_always_exempt(client, with_auth_configured):
    r = client.get("/api/healthz")
    assert r.status_code == 200


def test_static_dashboard_protected(client, with_auth_configured):
    assert client.get("/").status_code == 401
    assert client.get("/", auth=("admin", "s3cret")).status_code == 200


def test_websocket_rejected_without_credentials(client, with_auth_configured):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/ws"):
            pass


def test_websocket_accepted_with_credentials(client, with_auth_configured):
    with client.websocket_connect("/api/ws", auth=("admin", "s3cret")):
        pass
