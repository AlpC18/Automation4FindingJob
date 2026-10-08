"""
In-memory sliding window rate limiter for API endpoints.
Protects LLM credits, scraping infrastructure, and general server capacity
from accidental loops, brute force, and denial of wallet / denial of service.
"""

import time
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs

from fastapi import status
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Route-specific rate limits: (max_requests, window_seconds)
ROUTE_LIMITS: List[Tuple[str, int, int]] = [
    # Scraping endpoints: max 6 requests per minute
    ("/api/scrape/run", 6, 60),
    ("/api/scrape/portal-scan", 6, 60),
    # LLM / AI intelligence calls (wallet protection): max 20 per minute
    ("/api/intelligence/", 20, 60),
    # Auto apply execution: max 12 per minute
    ("/api/auto-apply/execute", 12, 60),
    # CV file upload and scanning: max 15 per minute
    ("/api/setup/cv", 15, 60),
]

# Default API rate limit: max 180 requests per minute
DEFAULT_API_LIMIT: Tuple[int, int] = (180, 60)

# Exempt paths that should never be rate limited
EXEMPT_PREFIXES = (
    "/system/health",
    "/system/runtime-config",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
)


class InMemoryRateLimiter:
    """Sliding-window counter for rate limiting client requests."""

    def __init__(self):
        # Key: (client_identifier, route_category) -> list of epoch timestamps
        self._history: Dict[Tuple[str, str], List[float]] = defaultdict(list)
        self._last_cleanup: float = time.time()

    def _cleanup_old_entries(self, now: float) -> None:
        """Prune timestamps older than 120 seconds to prevent memory growth."""
        if now - self._last_cleanup < 30.0:
            return
        self._last_cleanup = now
        cutoff = now - 120.0
        keys_to_delete = []
        for key, timestamps in self._history.items():
            valid = [ts for ts in timestamps if ts > cutoff]
            if valid:
                self._history[key] = valid
            else:
                keys_to_delete.append(key)
        for key in keys_to_delete:
            del self._history[key]

    def check(self, client_id: str, path: str, *, force: bool = False) -> Tuple[bool, int]:
        """
        Check if request is allowed.
        Returns: (is_allowed, retry_after_seconds)
        """
        # Testing environments skip rate limits unless explicitly forced in unit tests
        if not force and settings.ENVIRONMENT.lower() == "test":
            return True, 0

        # Exact path exemptions
        if path == "/" or any(path.endswith(exempt) for exempt in EXEMPT_PREFIXES):
            return True, 0

        now = time.time()
        self._cleanup_old_entries(now)

        # Determine route-specific limit or fallback to default
        max_requests, window_seconds = DEFAULT_API_LIMIT
        matched_category = "default"

        for prefix, limit_req, limit_win in ROUTE_LIMITS:
            if path.startswith(prefix) or prefix in path:
                max_requests = limit_req
                window_seconds = limit_win
                matched_category = prefix
                break

        key = (client_id, matched_category)
        cutoff = now - window_seconds
        recent_timestamps = [ts for ts in self._history[key] if ts > cutoff]

        if len(recent_timestamps) >= max_requests:
            oldest_relevant = recent_timestamps[0]
            retry_after = max(1, int(oldest_relevant + window_seconds - now))
            return False, retry_after

        recent_timestamps.append(now)
        self._history[key] = recent_timestamps
        return True, 0

    def reset(self) -> None:
        """Reset all rate limiter state (useful for test isolation)."""
        self._history.clear()
        self._last_cleanup = time.time()


limiter = InMemoryRateLimiter()


class RateLimitMiddleware:
    """ASGI middleware applying rate limits across HTTP endpoints."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # Do not rate limit CORS preflight requests
        if scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        client_info = scope.get("client")
        client_ip = client_info[0] if client_info else "127.0.0.1"

        # Check for forwarded IP behind reverse proxies
        headers = dict(scope.get("headers", []))
        forwarded_for = headers.get(b"x-forwarded-for", b"").decode("utf-8")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        allowed, retry_after = limiter.check(client_ip, path)
        if not allowed:
            logger.warning(
                "Rate limit exceeded for client %s on %s. Retry after %d s",
                client_ip, path, retry_after
            )
            body = b'{"detail":"Rate limit exceeded. Please wait before making more requests."}'
            await send({
                "type": "http.response.start",
                "status": status.HTTP_429_TOO_MANY_REQUESTS,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", str(retry_after).encode("ascii")),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)
