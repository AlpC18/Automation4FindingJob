"""Encrypted, tenant-scoped credentials for cloud LLM providers."""

from typing import Any

from backend.app.core.config import settings
from backend.app.core.database import get_db_connection
from backend.app.core.security import decrypt_secret, encrypt_secret

PROVIDER_ENV_KEYS = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}


def get_provider_api_key(provider: str) -> str:
    provider = provider.lower()
    if provider not in PROVIDER_ENV_KEYS:
        return ""
    conn = get_db_connection()
    try:
        row = conn.cursor()
        row.execute("SELECT encrypted_api_key FROM llm_provider_credentials WHERE provider = ?", (provider,))
        credential = row.fetchone()
        stored = credential[0] if credential and not isinstance(credential, dict) else (
            credential["encrypted_api_key"] if credential else ""
        )
        if stored:
            return decrypt_secret(stored)
    finally:
        conn.close()
    return str(getattr(settings, PROVIDER_ENV_KEYS[provider], "") or "").strip()


def get_provider_credential_status() -> list[dict[str, Any]]:
    providers = []
    for provider, env_name in PROVIDER_ENV_KEYS.items():
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM llm_provider_credentials WHERE provider = ?", (provider,))
            has_saved_key = cursor.fetchone() is not None
        finally:
            conn.close()
        has_environment_key = bool(getattr(settings, env_name, "").strip())
        providers.append({
            "provider": provider,
            "is_configured": has_saved_key or has_environment_key,
            "has_saved_key": has_saved_key,
            "managed_by_environment": has_environment_key and not has_saved_key,
        })
    return providers


def save_provider_api_key(provider: str, api_key: str) -> None:
    provider = provider.lower()
    if provider not in PROVIDER_ENV_KEYS:
        raise ValueError("Desteklenmeyen LLM sağlayıcısı.")
    if not api_key or len(api_key.strip()) < 8:
        raise ValueError("Geçerli bir API anahtarı girin.")
    encrypted = encrypt_secret(api_key.strip())
    conn = get_db_connection()
    try:
        conn.cursor().execute(
            """INSERT INTO llm_provider_credentials(provider, encrypted_api_key, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(provider) DO UPDATE SET encrypted_api_key = excluded.encrypted_api_key,
               updated_at = CURRENT_TIMESTAMP""",
            (provider, encrypted),
        )
        conn.commit()
    finally:
        conn.close()


def delete_provider_api_key(provider: str) -> None:
    provider = provider.lower()
    if provider not in PROVIDER_ENV_KEYS:
        raise ValueError("Desteklenmeyen LLM sağlayıcısı.")
    conn = get_db_connection()
    try:
        conn.cursor().execute("DELETE FROM llm_provider_credentials WHERE provider = ?", (provider,))
        conn.commit()
    finally:
        conn.close()
