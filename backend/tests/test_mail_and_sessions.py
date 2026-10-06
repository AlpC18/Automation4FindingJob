"""Mailbox connections (OAuth) and login sessions: the code that guards someone's inbox and account."""

import asyncio
import base64
import time
from datetime import datetime, timedelta

import httpx
import pytest

from backend.app.core import auth_sessions as sessions
from backend.app.core.database import init_auth_db
from backend.app.core.security import decrypt_secret, encrypt_secret
from backend.app.modules.outcome import oauth_mail_agent as mail_module

REAL_ASYNC_CLIENT = httpx.AsyncClient
agent = mail_module.oauth_mail_agent


def _web(monkeypatch, handler):
    monkeypatch.setattr(mail_module.httpx, "AsyncClient", lambda **kwargs: REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), **kwargs))


@pytest.fixture
def google_app(monkeypatch):
    monkeypatch.setattr(mail_module.settings, "GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setattr(mail_module.settings, "GOOGLE_CLIENT_SECRET", "client-secret")
    yield
    agent.disconnect("google")


def test_connecting_needs_configured_credentials(monkeypatch):
    monkeypatch.setattr(mail_module.settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(mail_module.settings, "DEMO_DATA_ENABLED", False)

    with pytest.raises(RuntimeError):
        agent.get_google_auth_url()
    with pytest.raises(RuntimeError):
        asyncio.run(agent.handle_google_callback("code"))
    assert agent.get_accounts_status()["google"]["auth_url"] is None


def test_google_connection_stores_encrypted_tokens_for_the_real_address(monkeypatch, google_app):
    def handler(request):
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "access-1", "refresh_token": "refresh-1", "expires_in": 3600, "scope": "gmail.readonly"})
        return httpx.Response(200, json={"email": "ada@example.test"})

    _web(monkeypatch, handler)

    result = asyncio.run(agent.handle_google_callback("auth-code"))
    status = agent.get_accounts_status()["google"]

    assert (result["status"], result["email"]) == ("SUCCESS", "ada@example.test")
    assert status["connected"] is True and status["email"] == "ada@example.test"
    assert "gmail.readonly" in agent.get_google_auth_url() and "gmail.send" not in agent.get_google_auth_url()
    assert agent.disconnect("google")["status"] == "SUCCESS"
    assert agent.get_accounts_status()["google"]["connected"] is False


def test_a_refused_or_anonymous_google_login_connects_nothing(monkeypatch, google_app):
    _web(monkeypatch, lambda request: httpx.Response(400, json={"error_description": "bad code"}))
    assert asyncio.run(agent.handle_google_callback("bad")) == {"status": "ERROR", "message": "bad code"}

    def no_email(request):
        return httpx.Response(200, json={"access_token": "a"} if request.url.host == "oauth2.googleapis.com" else {})

    _web(monkeypatch, no_email)
    assert asyncio.run(agent.handle_google_callback("code"))["status"] == "ERROR"
    assert agent.get_accounts_status()["google"]["connected"] is False


def _account(expires_in_seconds, refresh="refresh-1"):
    return {
        "access_token": encrypt_secret("old-token"), "refresh_token": encrypt_secret(refresh) if refresh else None,
        "expires_at": (datetime.now() + timedelta(seconds=expires_in_seconds)).strftime("%Y-%m-%d %H:%M:%S"),
    }


def test_access_tokens_are_refreshed_only_when_they_expire(monkeypatch, google_app):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"access_token": "new-token", "expires_in": 3600})

    _web(monkeypatch, handler)

    assert asyncio.run(agent._get_access_token("google", _account(3600))) == "old-token"
    assert asyncio.run(agent._get_access_token("google", _account(-10))) == "new-token"
    assert asyncio.run(agent._get_access_token("google", _account(-10, refresh=None))) == "old-token"
    assert asyncio.run(agent._get_access_token("yahoo", _account(-10))) is None
    assert len(calls) == 1 and b"grant_type=refresh_token" in calls[0].content

    _web(monkeypatch, lambda request: httpx.Response(401, json={}))
    assert asyncio.run(agent._get_access_token("google", _account(-10))) is None
    _web(monkeypatch, lambda request: httpx.Response(200, json={}))
    assert asyncio.run(agent._get_access_token("microsoft", _account(-10))) in (None, "old-token")


def test_expiry_is_read_defensively():
    assert agent._account_expired({"expires_at": None}) is True
    assert agent._account_expired({"expires_at": "soon"}) is True
    assert agent._account_expired({"expires_at": "2099-01-01T00:00:00Z"}) is False
    assert agent._account_expired({"expires_at": "2001-01-01 00:00:00"}) is True


def test_unread_gmail_is_read_including_nested_and_broken_bodies(monkeypatch):
    encoded = base64.urlsafe_b64encode("Mülakat daveti".encode()).decode().rstrip("=")

    def handler(request):
        if request.url.path.endswith("/messages"):
            assert request.url.params["q"] == "is:unread"
            return httpx.Response(200, json={"messages": [{"id": "m1"}]})
        return httpx.Response(200, json={"payload": {
            "headers": [{"name": "From", "value": "Sam Recruiter <sam@acme.test>"}, {"name": "Subject", "value": "Interview"}],
            "parts": [{"body": {}}, {"parts": [{"body": {"data": encoded}}]}],
        }})

    _web(monkeypatch, handler)

    messages = asyncio.run(agent._fetch_gmail_messages("token"))

    assert messages == [{"external_message_id": "gmail:m1", "sender_email": "sam@acme.test", "sender_name": "Sam Recruiter",
                         "subject": "Interview", "body_text": "Mülakat daveti"}]
    assert agent._decode_gmail_part({"body": {}}) == ""


def test_unread_outlook_mail_is_read(monkeypatch):
    def handler(request):
        assert request.headers["authorization"] == "Bearer token"
        return httpx.Response(200, json={"value": [{
            "id": "o1", "subject": "Offer", "body": {"content": "Congratulations"},
            "from": {"emailAddress": {"address": "hr@acme.test", "name": "HR"}},
        }]})

    _web(monkeypatch, handler)

    assert asyncio.run(agent._fetch_microsoft_messages("token")) == [{
        "external_message_id": "microsoft:o1", "sender_email": "hr@acme.test", "sender_name": "HR", "subject": "Offer", "body_text": "Congratulations",
    }]


@pytest.fixture
def account():
    init_auth_db()
    user = sessions.create_account(f"user-{time.time_ns()}@example.test", "a-long-password", email_verified=False)
    yield user
    sessions.delete_account_data(user["id"])


def test_session_tokens_reject_tampering_wrong_kind_and_expiry(account):
    token = sessions.issue_session_token(account["id"], account["email"])
    payload, signature = token.split(".")

    assert sessions.verify_token(token)["sub"] == account["id"]
    for bad in (payload + "x." + signature, payload + "." + signature[::-1], "not-a-token", sessions.issue_oauth_state(account["id"])):
        with pytest.raises(ValueError):
            sessions.verify_token(bad)
    with pytest.raises(ValueError):
        sessions.verify_token(sessions._issue_token({"sub": account["id"], "kind": "session"}, -5))
    assert sessions.verify_token(sessions.issue_oauth_state(account["id"]), "oauth_state")["sub"] == account["id"]


def test_a_session_needs_a_verified_active_account_at_the_current_version(account):
    token = sessions.issue_session_token(account["id"], account["email"])

    with pytest.raises(ValueError, match="not been verified"):
        sessions.authenticate_session(token)

    assert sessions.mark_email_verified(account["id"]) is True
    assert sessions.authenticate_session(token)["csrf_token"]
    assert account["id"] in sessions.list_active_tenant_ids()

    assert sessions.update_password(account["id"], "another-long-password") is True
    with pytest.raises(ValueError, match="revoked"):
        sessions.authenticate_session(token)
    assert sessions.verify_password("another-long-password", "md5$abc$def") is False
    assert sessions.verify_password("x", "garbage") is False


def test_security_links_work_once_and_are_not_reissued_within_a_minute(account):
    token = sessions.issue_security_token(account["id"], "reset_password", 3600)

    assert sessions.issue_security_token(account["id"], "reset_password", 3600) is None
    assert sessions.consume_security_token(token, "verify_email") is None
    assert sessions.consume_security_token(token, "reset_password") == account["id"]
    assert sessions.consume_security_token(token, "reset_password") is None
    assert sessions.get_security_email_user(account["email"].upper())["id"] == account["id"]
    assert sessions.get_security_email_user("nobody@example.test") is None


def test_security_emails_are_rate_limited_per_address(account):
    allowed = [sessions.allow_security_email_request(account["email"], "203.0.113.9", "reset_password", email_limit=2) for _ in range(3)]

    assert allowed == [True, True, False]


def test_deleting_an_account_removes_its_login_and_its_data(account):
    tenant_db = sessions.settings.DATA_PATH / "tenants" / f"{account['id']}.db"
    tenant_dir = sessions.settings.DATA_PATH / "tenants" / account["id"]
    tenant_dir.mkdir(parents=True, exist_ok=True)
    (tenant_dir / "queue.json").write_text("{}", encoding="utf-8")

    sessions.delete_account_data(account["id"])

    assert sessions.get_active_user(account["id"]) is None
    assert not tenant_db.exists() and not tenant_dir.exists()
    with pytest.raises(ValueError):
        sessions.delete_account_data("../..")
    with pytest.raises(ValueError, match="no longer exists"):
        sessions.authenticate_session(sessions.issue_session_token(account["id"], account["email"]))


def test_the_signing_key_is_created_locally_but_required_in_production(monkeypatch, tmp_path):
    monkeypatch.setattr(sessions.settings, "AUTH_SECRET_KEY", "")
    monkeypatch.setattr(sessions.settings, "APP_ENCRYPTION_KEY", "")
    monkeypatch.setattr(sessions.settings, "DATA_PATH", tmp_path)

    first = sessions._signing_key()

    assert first == sessions._signing_key() and len(first) >= 32
    assert oct((tmp_path / ".session-signing-key").stat().st_mode)[-3:] == "600"
    monkeypatch.setattr(sessions.settings, "ENVIRONMENT", "production")
    with pytest.raises(RuntimeError):
        sessions._signing_key()
