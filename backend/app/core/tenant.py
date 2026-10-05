"""Per-request tenant context shared by HTTP, WebSocket, and worker code."""

from contextvars import ContextVar, Token
from pathlib import Path
from typing import Optional
import re

from backend.app.core.config import settings

_current_tenant_id: ContextVar[Optional[str]] = ContextVar("career_agent_tenant_id", default=None)


def get_tenant_id() -> Optional[str]:
    return _current_tenant_id.get()


def set_tenant_id(tenant_id: Optional[str]) -> Token:
    return _current_tenant_id.set(tenant_id)


def reset_tenant_id(token: Token) -> None:
    _current_tenant_id.reset(token)


def tenant_data_path(filename: str) -> Path:
    """Resolve private file-backed state into the active tenant directory."""
    tenant_id = get_tenant_id()
    if not tenant_id:
        return settings.DATA_PATH / filename
    safe_id = re.sub(r"[^a-zA-Z0-9]", "", tenant_id)
    return settings.DATA_PATH / "tenants" / safe_id / filename
