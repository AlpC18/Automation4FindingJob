"""Encrypted account-level SMTP configuration with environment fallback."""

from __future__ import annotations

import json
import re
import smtplib
from typing import Any

from backend.app.core.config import settings
from backend.app.core.database import get_db_connection
from backend.app.core.security import decrypt_secret, encrypt_secret

SMTP_ID = "account"
_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


def _environment_config() -> dict[str, Any]:
    return {
        "host": settings.SMTP_HOST.strip(),
        "port": int(settings.SMTP_PORT),
        "username": settings.SMTP_USER.strip(),
        "password": settings.SMTP_PASS,
        "from_email": settings.SMTP_FROM_EMAIL.strip() or settings.SMTP_USER.strip(),
        "use_tls": bool(settings.SMTP_USE_TLS),
        "source": "environment",
    }


def get_smtp_configuration() -> dict[str, Any]:
    """Return decrypted settings only to server code; never expose the password."""
    conn = get_db_connection()
    try:
        row = conn.cursor().execute(
            "SELECT encrypted_config FROM smtp_credentials WHERE id = ?", (SMTP_ID,)
        ).fetchone()
    finally:
        conn.close()
    encrypted = row["encrypted_config"] if isinstance(row, dict) else (row[0] if row else "")
    if not encrypted:
        return _environment_config()
    try:
        config = json.loads(decrypt_secret(encrypted))
    except Exception as exc:
        raise RuntimeError("Kayıtlı SMTP ayarları açılamadı; uygulama şifreleme anahtarını kontrol edin.") from exc
    return {
        "host": str(config.get("host", "")).strip(),
        "port": int(config.get("port", 587)),
        "username": str(config.get("username", "")).strip(),
        "password": str(config.get("password", "")),
        "from_email": str(config.get("from_email", "")).strip(),
        "use_tls": bool(config.get("use_tls", True)),
        "source": "account",
    }


def smtp_configuration_status() -> dict[str, Any]:
    config = get_smtp_configuration()
    configured = bool(config["host"] and config["from_email"] and (not config["username"] or config["password"]))
    return {
        "configured": configured,
        "source": config["source"] if configured else "not_configured",
        "host": config["host"],
        "port": config["port"],
        "username": config["username"],
        "from_email": config["from_email"],
        "use_tls": config["use_tls"],
        "has_password": bool(config["password"]),
        "requires_encryption_key": configured and config["source"] == "account",
    }


def save_smtp_configuration(
    *, host: str, port: int, username: str, password: str, from_email: str, use_tls: bool
) -> None:
    host = host.strip()
    username = username.strip()
    from_email = from_email.strip()
    password = password or ""
    if not host or len(host) > 255 or any(char in host for char in "\r\n /\\"):
        raise ValueError("Geçerli bir SMTP sunucusu girin.")
    if not 1 <= int(port) <= 65535:
        raise ValueError("SMTP portu 1–65535 arasında olmalı.")
    if not _EMAIL.fullmatch(from_email):
        raise ValueError("Gönderici için geçerli bir e-posta adresi girin.")
    if username and not password:
        current = get_smtp_configuration()
        if current["username"] == username and current["host"] == host:
            password = current["password"]
    if username and not password:
        raise ValueError("SMTP kullanıcı adı için parola gerekli. Kayıtlı parolayı değiştirmiyorsan alanı boş bırak.")
    if len(password) > 1024 or len(username) > 254:
        raise ValueError("SMTP kimlik bilgisi izin verilen uzunluğu aşıyor.")

    encrypted = encrypt_secret(json.dumps({
        "host": host,
        "port": int(port),
        "username": username,
        "password": password,
        "from_email": from_email,
        "use_tls": bool(use_tls),
    }, separators=(",", ":")))
    conn = get_db_connection()
    try:
        conn.cursor().execute(
            """INSERT INTO smtp_credentials(id, encrypted_config, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(id) DO UPDATE SET encrypted_config = excluded.encrypted_config,
               updated_at = CURRENT_TIMESTAMP""",
            (SMTP_ID, encrypted),
        )
        conn.commit()
    finally:
        conn.close()


def delete_smtp_configuration() -> None:
    conn = get_db_connection()
    try:
        conn.cursor().execute("DELETE FROM smtp_credentials WHERE id = ?", (SMTP_ID,))
        conn.commit()
    finally:
        conn.close()


def test_smtp_connection() -> dict[str, Any]:
    """Connect and authenticate without sending a test message."""
    config = get_smtp_configuration()
    if not config["host"] or not config["from_email"]:
        return {"status": "not_configured", "message": "SMTP ayarları tamamlanmadı."}
    if config["username"] and not config["password"]:
        return {"status": "not_configured", "message": "SMTP uygulama parolası eksik. E-posta ayarlarına kaydedin."}
    try:
        with smtplib.SMTP(config["host"], config["port"], timeout=15) as server:
            server.ehlo()
            if config["use_tls"]:
                server.starttls()
                server.ehlo()
            if config["username"]:
                server.login(config["username"], config["password"])
    except Exception as exc:
        return {"status": "failed", "error_type": type(exc).__name__, "message": "SMTP sunucusuna bağlanılamadı veya oturum açılamadı."}
    return {"status": "connected", "message": "SMTP bağlantısı doğrulandı; test e-postası gönderilmedi."}
