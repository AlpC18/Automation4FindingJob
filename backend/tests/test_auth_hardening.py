"""Account security flows using an isolated control and tenant database."""

import re
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from backend.app.core import auth_sessions
from backend.app.core.config import settings
from backend.app.core.database import init_auth_db, init_db
from backend.app.core.auth_sessions import create_account, get_active_user, issue_security_token, issue_session_token
from backend.app.main import app


@pytest.fixture
def auth_client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATA_PATH", tmp_path)
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'control.db'}")
    monkeypatch.setattr(settings, "MULTI_TENANT_ENABLED", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "AUTH_SECRET_KEY", "test-signing-secret-at-least-32-characters")
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    init_db()
    init_auth_db()
    return TestClient(app)


def test_email_verification_is_required_when_smtp_is_configured(auth_client, monkeypatch):
    from backend.app.api.routers import auth as auth_router_module

    sent = []
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "accounts@example.test")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASS", "")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(auth_router_module, "send_security_email", lambda recipient, subject, body: sent.append(body))

    response = auth_client.post("/api/auth/register", json={"email": "new@example.test", "password": "a-very-long-password"})
    assert response.status_code == 201
    assert response.json()["verification_required"] is True
    assert response.cookies.get("career_session") is None
    token_match = re.search(r"token=([^\s]+)", sent[0])
    assert token_match
    raw_token = unquote(token_match.group(1))

    verified = auth_client.get(f"/api/auth/verify-email?token={raw_token}", follow_redirects=False)
    assert verified.status_code == 303
    assert verified.headers["location"].endswith("/?verified=1")


def test_account_registration_does_not_leak_internal_errors(auth_client, monkeypatch):
    from backend.app.api.routers import auth as auth_router_module

    def fail_registration(*_args, **_kwargs):
        raise RuntimeError("database password must never be returned")

    monkeypatch.setattr(auth_router_module, "create_account", fail_registration)
    response = auth_client.post(
        "/api/auth/register",
        json={"email": "failure@example.test", "password": "a-very-long-password"},
    )
    assert response.status_code == 503
    assert "database password" not in response.text
    assert response.json()["detail"] == "Hesap oluşturulamadı. Lütfen daha sonra tekrar deneyin."


def test_login_does_not_return_auth_configuration_errors(auth_client, monkeypatch):
    from backend.app.api.routers import auth as auth_router_module

    def fail_login(*_args, **_kwargs):
        raise RuntimeError("private signing secret is invalid")

    monkeypatch.setattr(auth_router_module, "verify_account", fail_login)
    response = auth_client.post(
        "/api/auth/login",
        json={"email": "candidate@example.test", "password": "a-very-long-password"},
    )
    assert response.status_code == 503
    assert "private signing secret" not in response.text
    assert response.json()["detail"] == "Giriş hizmeti şu anda kullanılamıyor."


def test_cookie_mutations_require_csrf_and_account_deletion_confirmation(auth_client):
    registered = auth_client.post(
        "/api/auth/register",
        json={"email": "delete-me@example.test", "password": "a-very-long-password"},
    )
    assert registered.status_code == 201
    user = registered.json()["user"]
    csrf = registered.json()["csrf_token"]

    without_csrf = auth_client.post("/api/auth/logout")
    assert without_csrf.status_code == 403
    with_csrf = auth_client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert with_csrf.status_code == 200

    # Re-authenticate and require both an exact account email and password to delete.
    login = auth_client.post(
        "/api/auth/login",
        json={"email": "delete-me@example.test", "password": "a-very-long-password"},
    )
    assert login.status_code == 200
    csrf = login.json()["csrf_token"]
    deleted = auth_client.request(
        "DELETE", "/api/auth/account",
        json={"email": "delete-me@example.test", "password": "a-very-long-password"},
        headers={"X-CSRF-Token": csrf},
    )
    assert deleted.status_code == 204
    assert get_active_user(user["id"]) is None


def test_login_attempts_are_rate_limited_and_password_reset_revokes_sessions(auth_client):
    user = create_account("reset@example.test", "old-password-long", email_verified=True)
    for _ in range(10):
        assert auth_client.post(
            "/api/auth/login", json={"email": user["email"], "password": "incorrect-password"}
        ).status_code == 401
    limited = auth_client.post(
        "/api/auth/login", json={"email": user["email"], "password": "incorrect-password"}
    )
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "900"

    old_session = issue_session_token(user["id"], user["email"], user["session_version"])
    token = issue_security_token(user["id"], "password_reset", 1800)
    reset = auth_client.post(
        "/api/auth/password-reset", json={"token": token, "new_password": "new-password-long"}
    )
    assert reset.status_code == 200
    assert auth_sessions.verify_account(user["email"], "old-password-long") is None
    assert auth_sessions.verify_account(user["email"], "new-password-long") is not None
    with pytest.raises(ValueError):
        auth_sessions.authenticate_session(old_session)
