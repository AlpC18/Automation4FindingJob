"""Password and signed cookie session helpers for multi-tenant accounts."""

import base64
import hashlib
import hmac
import json
import secrets
import shutil
import time
import uuid
from typing import Any, Dict, Optional
from pathlib import Path

from backend.app.core.config import settings
from backend.app.core.database import get_control_db_connection, init_tenant_db, is_postgres_database

SESSION_TTL_SECONDS = 60 * 60 * 24


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _signing_key() -> bytes:
    secret = settings.AUTH_SECRET_KEY.strip() or settings.APP_ENCRYPTION_KEY.strip()
    if not secret and settings.ENVIRONMENT.lower() != "production":
        key_path = settings.DATA_PATH / ".session-signing-key"
        key_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            secret = key_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            generated = secrets.token_urlsafe(48)
            try:
                with key_path.open("x", encoding="utf-8") as secret_file:
                    secret_file.write(generated)
                key_path.chmod(0o600)
                secret = generated
            except FileExistsError:
                secret = key_path.read_text(encoding="utf-8").strip()
    if len(secret) < 32:
        raise RuntimeError("AUTH_SECRET_KEY (minimum 32 characters) must be configured for multi-tenant sessions")
    return secret.encode("utf-8")


def _issue_token(claims: Dict[str, Any], expires_in: int) -> str:
    now = int(time.time())
    payload = {**claims, "iat": now, "exp": now + expires_in}
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(_signing_key(), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_b64encode(signature)}"


def issue_session_token(user_id: str, email: str, session_version: int = 0, csrf_token: Optional[str] = None) -> str:
    return _issue_token(
        {"sub": user_id, "email": email, "sv": session_version, "csrf": csrf_token or secrets.token_urlsafe(32), "kind": "session"},
        SESSION_TTL_SECONDS,
    )


def issue_oauth_state(user_id: str) -> str:
    return _issue_token({"sub": user_id, "kind": "oauth_state", "nonce": secrets.token_urlsafe(18)}, 600)


def verify_token(token: str, expected_kind: str = "session") -> Dict[str, Any]:
    try:
        payload_part, signature_part = token.split(".", 1)
        expected = hmac.new(_signing_key(), payload_part.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(signature_part)):
            raise ValueError("invalid signature")
        payload = json.loads(_b64decode(payload_part))
        if payload.get("kind") != expected_kind or int(payload.get("exp", 0)) <= int(time.time()):
            raise ValueError("expired or incorrect token")
        if not isinstance(payload.get("sub"), str):
            raise ValueError("missing subject")
        return payload
    except Exception as exc:
        raise ValueError("Invalid or expired session") from exc


def get_active_user(user_id: str) -> Optional[Dict[str, str]]:
    conn = get_control_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, email_verified, session_version FROM auth_users WHERE id = ? AND is_active = 1", (user_id,))
        row = cursor.fetchone()
        return {
            "id": row["id"], "email": row["email"],
            "email_verified": bool(row["email_verified"]),
            "session_version": int(row["session_version"] or 0),
        } if row else None
    finally:
        conn.close()


def list_active_tenant_ids() -> list[str]:
    """Return active user IDs for isolated scheduled processing."""
    conn = get_control_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM auth_users WHERE is_active = 1 ORDER BY created_at")
        return [row["id"] for row in cursor.fetchall()]
    finally:
        conn.close()


def authenticate_session(token: str) -> Dict[str, Any]:
    claims = verify_token(token)
    user = get_active_user(claims["sub"])
    if not user:
        raise ValueError("Account is inactive or no longer exists")
    if not user["email_verified"]:
        raise ValueError("Email address has not been verified")
    if int(claims.get("sv", -1)) != user["session_version"] or not claims.get("csrf"):
        raise ValueError("Session was revoked or is missing CSRF state")
    user["csrf_token"] = claims["csrf"]
    return user


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _derive_password_hash(password, salt)
    return f"scrypt${_b64encode(salt)}${_b64encode(digest)}"


def _derive_password_hash(password: str, salt: bytes) -> bytes:
    if hasattr(hashlib, "scrypt"):
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64)
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    return Scrypt(salt=salt, length=64, n=2**14, r=8, p=1).derive(password.encode("utf-8"))


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_part, digest_part = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        salt = _b64decode(salt_part)
        expected = _b64decode(digest_part)
        actual = _derive_password_hash(password, salt)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_account(email: str, password: str, *, email_verified: bool = False) -> Dict[str, Any]:
    user_id = uuid.uuid4().hex
    conn = get_control_db_connection()
    try:
        conn.cursor().execute(
            "INSERT INTO auth_users (id, email, password_hash, email_verified) VALUES (?, ?, ?, ?)",
            (user_id, email.strip().lower(), hash_password(password), int(email_verified)),
        )
        conn.commit()
    finally:
        conn.close()
    try:
        init_tenant_db(user_id)
    except Exception:
        cleanup = get_control_db_connection()
        cleanup.cursor().execute("DELETE FROM auth_users WHERE id = ?", (user_id,))
        cleanup.commit()
        cleanup.close()
        raise
    return {"id": user_id, "email": email.strip().lower(), "email_verified": email_verified, "session_version": 0}


def verify_account(email: str, password: str) -> Optional[Dict[str, str]]:
    conn = get_control_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, email, password_hash, email_verified, session_version FROM auth_users WHERE email = ? AND is_active = 1",
            (email.strip().lower(),),
        )
        row = cursor.fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            return None
        return {
            "id": row["id"], "email": row["email"],
            "email_verified": bool(row["email_verified"]),
            "session_version": int(row["session_version"] or 0),
        }
    finally:
        conn.close()


def issue_security_token(user_id: str, purpose: str, expires_in: int) -> Optional[str]:
    raw_token = secrets.token_urlsafe(36)
    token_hash = hashlib.sha256(raw_token.encode("ascii")).hexdigest()
    now = time.time()
    conn = get_control_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT expires_at FROM auth_security_tokens WHERE user_id = ? AND purpose = ? AND used_at IS NULL AND expires_at > ? ORDER BY expires_at DESC LIMIT 1",
            (user_id, purpose, now),
        )
        active = cursor.fetchone()
        if active and now - (float(active["expires_at"]) - expires_in) < 60:
            return None
        cursor.execute(
            "UPDATE auth_security_tokens SET used_at = ? WHERE user_id = ? AND purpose = ? AND used_at IS NULL",
            (now, user_id, purpose),
        )
        cursor.execute(
            "INSERT INTO auth_security_tokens(token_hash, user_id, purpose, expires_at) VALUES (?, ?, ?, ?)",
            (token_hash, user_id, purpose, now + expires_in),
        )
        conn.commit()
    finally:
        conn.close()
    return raw_token


def consume_security_token(raw_token: str, purpose: str) -> Optional[str]:
    token_hash = hashlib.sha256(raw_token.encode("ascii", errors="ignore")).hexdigest()
    now = time.time()
    conn = get_control_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id FROM auth_security_tokens WHERE token_hash = ? AND purpose = ? AND used_at IS NULL AND expires_at > ?",
            (token_hash, purpose, now),
        )
        row = cursor.fetchone()
        if not row:
            return None
        cursor.execute(
            "UPDATE auth_security_tokens SET used_at = ? WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
            (now, token_hash, now),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return None
        conn.commit()
        return row["user_id"]
    finally:
        conn.close()


def mark_email_verified(user_id: str) -> bool:
    conn = get_control_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE auth_users SET email_verified = 1 WHERE id = ? AND is_active = 1", (user_id,))
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def update_password(user_id: str, password: str) -> bool:
    conn = get_control_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE auth_users SET password_hash = ?, session_version = session_version + 1 WHERE id = ? AND is_active = 1",
            (hash_password(password), user_id),
        )
        changed = cursor.rowcount == 1
        cursor.execute("DELETE FROM auth_security_tokens WHERE user_id = ?", (user_id,))
        conn.commit()
        return changed
    finally:
        conn.close()


def get_security_email_user(email: str) -> Optional[Dict[str, str]]:
    conn = get_control_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, email, email_verified FROM auth_users WHERE email = ? AND is_active = 1",
            (email.strip().lower(),),
        )
        row = cursor.fetchone()
        return {"id": row["id"], "email": row["email"], "email_verified": bool(row["email_verified"])} if row else None
    finally:
        conn.close()


def login_rate_limited(email: str, ip_address: str, *, window_seconds: int = 900,
                       email_failure_limit: int = 10, ip_failure_limit: int = 30) -> bool:
    cutoff = time.time() - window_seconds
    conn = get_control_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) AS total FROM auth_login_attempts WHERE email = ? AND attempted_at >= ? AND succeeded = 0",
            (email.strip().lower(), cutoff),
        )
        email_count = cursor.fetchone()["total"]
        cursor.execute(
            "SELECT COUNT(*) AS total FROM auth_login_attempts WHERE ip_address = ? AND attempted_at >= ? AND succeeded = 0",
            (ip_address, cutoff),
        )
        ip_count = cursor.fetchone()["total"]
        return email_count >= email_failure_limit or ip_count >= ip_failure_limit
    finally:
        conn.close()


def record_login_attempt(email: str, ip_address: str, succeeded: bool) -> None:
    conn = get_control_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO auth_login_attempts(id, email, ip_address, succeeded, attempted_at) VALUES (?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, email.strip().lower(), ip_address[:128], int(succeeded), time.time()),
        )
        cursor.execute("DELETE FROM auth_login_attempts WHERE attempted_at < ?", (time.time() - 30 * 86400,))
        conn.commit()
    finally:
        conn.close()


def allow_security_email_request(email: str, ip_address: str, purpose: str,
                                 *, window_seconds: int = 3600,
                                 email_limit: int = 3, ip_limit: int = 20) -> bool:
    normalized = email.strip().lower()
    safe_ip = ip_address[:128]
    cutoff = time.time() - window_seconds
    conn = get_control_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) AS total FROM auth_security_requests WHERE email = ? AND purpose = ? AND requested_at >= ?",
            (normalized, purpose, cutoff),
        )
        email_count = cursor.fetchone()["total"]
        cursor.execute(
            "SELECT COUNT(*) AS total FROM auth_security_requests WHERE ip_address = ? AND requested_at >= ?",
            (safe_ip, cutoff),
        )
        ip_count = cursor.fetchone()["total"]
        allowed = email_count < email_limit and ip_count < ip_limit
        cursor.execute(
            "INSERT INTO auth_security_requests(id, email, ip_address, purpose, requested_at) VALUES (?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, normalized, safe_ip, purpose, time.time()),
        )
        cursor.execute("DELETE FROM auth_security_requests WHERE requested_at < ?", (cutoff - 7 * 86400,))
        conn.commit()
        return allowed
    finally:
        conn.close()


def delete_account_data(user_id: str) -> None:
    """Revoke identity and remove only the authenticated user's data store."""
    safe_id = "".join(char for char in user_id if char.isalnum())
    if not safe_id:
        raise ValueError("Invalid account identifier")
    conn = get_control_db_connection()
    try:
        if is_postgres_database():
            conn.cursor().execute(f'DROP SCHEMA IF EXISTS "tenant_{safe_id}" CASCADE')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM auth_security_tokens WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM auth_users WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
    if not is_postgres_database():
        database_path = settings.DATA_PATH / "tenants" / f"{safe_id}.db"
        for suffix in ("", "-wal", "-shm"):
            Path(f"{database_path}{suffix}").unlink(missing_ok=True)
    tenant_directory = settings.DATA_PATH / "tenants" / safe_id
    if tenant_directory.is_dir():
        shutil.rmtree(tenant_directory)
