"""Runtime authentication and at-rest secret protection."""

import base64
import hmac
import os
import secrets
from urllib.parse import parse_qs
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader, APIKeyQuery

from backend.app.core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)


def validate_api_key(api_key: Optional[str]) -> None:
    """Validate an API key value for HTTP and WebSocket callers."""
    expected = settings.API_AUTH_TOKEN.strip()
    if not expected:
        return
    if not api_key or not hmac.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçerli X-API-Key gerekli.",
            headers={"WWW-Authenticate": "ApiKey"},
        )


def is_valid_api_key(api_key: Optional[str]) -> bool:
    expected = settings.API_AUTH_TOKEN.strip()
    return not expected or bool(api_key and hmac.compare_digest(api_key, expected))


class APIKeyMiddleware:
    """Protect HTTP and WebSocket traffic, including browser WebSockets."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # CORS owns browser preflight validation. Requiring the API key here
        # would reject OPTIONS before CORSMiddleware can add its response
        # headers, making authenticated browser clients unusable.
        is_preflight = scope.get("type") == "http" and scope.get("method") == "OPTIONS"
        is_http_or_ws = scope.get("type") in ("http", "websocket")
        path = scope.get("path", "")

        if is_http_or_ws and settings.MULTI_TENANT_ENABLED and not is_preflight:
            public_paths = {
                f"{settings.API_V1_PREFIX}/auth/mode",
                f"{settings.API_V1_PREFIX}/auth/login",
                f"{settings.API_V1_PREFIX}/auth/register",
                f"{settings.API_V1_PREFIX}/auth/resend-verification",
                f"{settings.API_V1_PREFIX}/auth/verify-email",
                f"{settings.API_V1_PREFIX}/auth/password-reset-request",
                f"{settings.API_V1_PREFIX}/auth/password-reset",
                f"{settings.API_V1_PREFIX}/system/health",
                f"{settings.API_V1_PREFIX}/system/runtime-config",
            }
            oauth_callback = path.endswith(("/oauth/google/callback", "/oauth/microsoft/callback"))
            if path.startswith(f"{settings.API_V1_PREFIX}/") and path not in public_paths and not oauth_callback:
                headers = dict(scope.get("headers", []))
                authorization = headers.get(b"authorization", b"").decode("utf-8")
                bearer = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
                cookie_header = headers.get(b"cookie", b"").decode("utf-8")
                session_cookie = ""
                for part in cookie_header.split(";"):
                    key, separator, value = part.strip().partition("=")
                    if separator and key == "career_session":
                        session_cookie = value
                        break
                try:
                    from backend.app.core.auth_sessions import authenticate_session
                    from backend.app.core.tenant import reset_tenant_id, set_tenant_id

                    user = authenticate_session(bearer or session_cookie)
                except (ValueError, RuntimeError):
                    await self._unauthorized(scope, send)
                    return
                if (
                    session_cookie
                    and not bearer
                    and scope.get("method", "GET").upper() in {"POST", "PUT", "PATCH", "DELETE"}
                ):
                    csrf_token = headers.get(b"x-csrf-token", b"").decode("utf-8")
                    expected_csrf = user.get("csrf_token", "")
                    if not expected_csrf or not csrf_token or not hmac.compare_digest(csrf_token, expected_csrf):
                        await self._forbidden(scope, send)
                        return
                origin = headers.get(b"origin", b"").decode("utf-8")
                if (
                    session_cookie
                    and not bearer
                    and scope.get("method", "GET").upper() in {"POST", "PUT", "PATCH", "DELETE"}
                    and origin
                    and origin not in {item.strip() for item in settings.CORS_ORIGINS.split(",") if item.strip()}
                ):
                    await self._forbidden(scope, send)
                    return
                scope.setdefault("state", {})["auth_user"] = user
                tenant_token = set_tenant_id(user["id"])
                try:
                    await self.app(scope, receive, send)
                finally:
                    reset_tenant_id(tenant_token)
                return

        if (
            scope.get("type") in ("http", "websocket")
            and not settings.MULTI_TENANT_ENABLED
            and settings.API_AUTH_TOKEN.strip()
            and not is_preflight
        ):
            headers = dict(scope.get("headers", []))
            header_token = headers.get(b"x-api-key", b"").decode("utf-8")
            query = parse_qs(scope.get("query_string", b"").decode("utf-8"))
            query_token = query.get("api_key", [""])[0]
            if not is_valid_api_key(header_token or query_token):
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                else:
                    body = b'{"detail":"Gecerli X-API-Key gerekli."}'
                    await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"application/json")]})
                    await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)

    @staticmethod
    async def _unauthorized(scope, send):
        if scope.get("type") == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        body = b'{"detail":"Valid account session required."}'
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [(b"content-type", b"application/json"), (b"www-authenticate", b"Bearer")],
        })
        await send({"type": "http.response.body", "body": body})

    @staticmethod
    async def _forbidden(scope, send):
        if scope.get("type") == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        body = b'{"detail":"Cross-origin request rejected."}'
        await send({"type": "http.response.start", "status": 403, "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": body})


def require_api_key(
    api_key: Optional[str] = Security(api_key_header),
    query_api_key: Optional[str] = Security(api_key_query),
) -> None:
    """Require X-API-Key whenever API_AUTH_TOKEN is configured."""
    validate_api_key(api_key or query_api_key)


def _fernet():
    key = settings.APP_ENCRYPTION_KEY.strip()
    if not key:
        if settings.ENVIRONMENT.lower() == "production":
            return None
        key_path = settings.DATA_PATH / ".app_encryption_key"
        key_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            key = key_path.read_text(encoding="ascii").strip()
        except FileNotFoundError:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode("ascii")
            try:
                descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                key = key_path.read_text(encoding="ascii").strip()
            else:
                with os.fdopen(descriptor, "w", encoding="ascii") as key_file:
                    key_file.write(key)
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode())
    except Exception as exc:
        raise RuntimeError("APP_ENCRYPTION_KEY geçerli bir Fernet anahtarı olmalı.") from exc


def encrypt_secret(value: str) -> str:
    """Encrypt a value with the configured key or the local development key."""
    if not value:
        return value
    fernet = _fernet()
    if not fernet:
        raise RuntimeError("Secret saklamak için APP_ENCRYPTION_KEY tanımlayın.")
    return "fernet$" + fernet.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    """Decrypt encrypted values while remaining compatible with old plaintext data."""
    if not value or not value.startswith("fernet$"):
        return value
    fernet = _fernet()
    if not fernet:
        raise RuntimeError("Şifreli secret'ı açmak için APP_ENCRYPTION_KEY gerekli.")
    return fernet.decrypt(value[7:].encode("ascii")).decode("utf-8")


def generate_encryption_key() -> str:
    try:
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode("ascii")
    except ImportError:
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
