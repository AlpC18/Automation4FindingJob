import json

import pytest
from cryptography.fernet import Fernet

from backend.app.core.config import settings
from backend.app.core.database import get_db_connection, init_db, init_tenant_db, use_tenant
from backend.app.core.security import decrypt_secret
from backend.app.core.smtp_credentials import (
    get_smtp_configuration,
    save_smtp_configuration,
    smtp_configuration_status,
    test_smtp_connection,
)


@pytest.fixture
def isolated_database(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATA_PATH", tmp_path)
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'control.db'}")
    monkeypatch.setattr(settings, "MULTI_TENANT_ENABLED", True)
    monkeypatch.setattr(settings, "APP_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASS", "")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "")
    init_db()
    return tmp_path


def _save(host="smtp.example.test", username="mailer@example.test", password="mail-secret"):
    save_smtp_configuration(
        host=host,
        port=587,
        username=username,
        password=password,
        from_email="mailer@example.test",
        use_tls=True,
    )


def test_account_smtp_password_is_encrypted_and_never_in_status(isolated_database):
    _save()

    status = smtp_configuration_status()
    conn = get_db_connection()
    try:
        raw_value = conn.cursor().execute(
            "SELECT encrypted_config FROM smtp_credentials WHERE id = 'account'"
        ).fetchone()[0]
    finally:
        conn.close()

    assert status["configured"] is True
    assert status["source"] == "account"
    assert "password" not in status
    assert raw_value.startswith("fernet$")
    assert "mail-secret" not in raw_value
    assert json.loads(decrypt_secret(raw_value))["password"] == "mail-secret"


def test_blank_password_preserves_saved_secret_only_for_same_account_settings(isolated_database):
    _save()
    save_smtp_configuration(
        host="smtp.example.test",
        port=587,
        username="mailer@example.test",
        password="",
        from_email="new-sender@example.test",
        use_tls=True,
    )

    assert get_smtp_configuration()["password"] == "mail-secret"
    with pytest.raises(ValueError, match="parola gerekli"):
        save_smtp_configuration(
            host="smtp.other.test",
            port=587,
            username="other@example.test",
            password="",
            from_email="other@example.test",
            use_tls=True,
        )


def test_environment_fallback_and_unconfigured_state_are_truthful(isolated_database, monkeypatch):
    status = smtp_configuration_status()
    assert status["configured"] is False
    assert status["source"] == "not_configured"

    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.env.test")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "env@example.test")
    monkeypatch.setattr(settings, "SMTP_USER", "env-user")
    monkeypatch.setattr(settings, "SMTP_PASS", "env-secret")
    status = smtp_configuration_status()
    assert status["configured"] is True
    assert status["source"] == "environment"
    assert "password" not in status


def test_smtp_credentials_are_isolated_per_tenant(isolated_database):
    init_tenant_db("tenant-a")
    init_tenant_db("tenant-b")

    with use_tenant("tenant-a"):
        _save(host="smtp.a.test", username="a@example.test", password="a-secret")
        assert get_smtp_configuration()["host"] == "smtp.a.test"
    with use_tenant("tenant-b"):
        assert smtp_configuration_status()["source"] == "not_configured"
        _save(host="smtp.b.test", username="b@example.test", password="b-secret")
        assert get_smtp_configuration()["host"] == "smtp.b.test"
    with use_tenant("tenant-a"):
        assert get_smtp_configuration()["password"] == "a-secret"


def test_connection_check_authenticates_but_never_sends_email(isolated_database, monkeypatch):
    _save()
    calls = {"starttls": 0, "login": 0, "send": 0}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("smtp.example.test", 587, 15)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def ehlo(self):
            return None

        def starttls(self):
            calls["starttls"] += 1

        def login(self, username, password):
            assert (username, password) == ("mailer@example.test", "mail-secret")
            calls["login"] += 1

        def send_message(self, _message):
            calls["send"] += 1

    monkeypatch.setattr("backend.app.core.smtp_credentials.smtplib.SMTP", FakeSMTP)

    result = test_smtp_connection()

    assert result["status"] == "connected"
    assert calls == {"starttls": 1, "login": 1, "send": 0}
