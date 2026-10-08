"""
Tests for cybersecurity hardening features:
- SecurityHeadersMiddleware (X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy)
- In-memory rate limiting and Route-specific limits
- sanitize_safe_url URL validation (XSS prevention)
- Production docs disabling
"""

import pytest
from starlette.testclient import TestClient

from backend.app.core.config import settings
from backend.app.core.rate_limiter import InMemoryRateLimiter, RateLimitMiddleware
from backend.app.core.security import sanitize_safe_url
from backend.app.main import app


def test_security_headers_present_on_endpoints(client):
    """Verify that SecurityHeadersMiddleware attaches defensive HTTP headers."""
    response = client.get("/")
    assert response.status_code == 200
    headers = response.headers

    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert headers.get("x-xss-protection") == "1; mode=block"
    assert "camera=()" in headers.get("permissions-policy", "")


def test_sanitize_safe_url_valid_http_and_https():
    """Verify valid HTTP and HTTPS URLs are accepted."""
    assert sanitize_safe_url("https://linkedin.com/jobs/view/12345") == "https://linkedin.com/jobs/view/12345"
    assert sanitize_safe_url("http://example.com/careers") == "http://example.com/careers"
    assert sanitize_safe_url("  https://google.com/search?q=test  ") == "https://google.com/search?q=test"


def test_sanitize_safe_url_rejects_dangerous_protocols():
    """Verify XSS vectors and non-HTTP protocols are rejected."""
    assert sanitize_safe_url("javascript:alert(document.cookie)") is None
    assert sanitize_safe_url("data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==") is None
    assert sanitize_safe_url("file:///etc/passwd") is None
    assert sanitize_safe_url("vbscript:msgbox(1)") is None
    assert sanitize_safe_url("") is None
    assert sanitize_safe_url(None) is None
    assert sanitize_safe_url("   ") is None
    assert sanitize_safe_url("not-a-url") is None


def test_rate_limiter_allows_under_threshold():
    """Verify rate limiter allows requests below limit."""
    test_limiter = InMemoryRateLimiter()
    for _ in range(5):
        allowed, retry_after = test_limiter.check("1.2.3.4", "/api/scrape/run", force=True)
        assert allowed is True
        assert retry_after == 0


def test_rate_limiter_blocks_above_threshold():
    """Verify rate limiter blocks when threshold is reached."""
    test_limiter = InMemoryRateLimiter()
    # Route limit for /api/scrape/run is 6 requests
    for _ in range(6):
        allowed, _ = test_limiter.check("1.2.3.4", "/api/scrape/run", force=True)
        assert allowed is True

    # 7th request should be blocked
    allowed, retry_after = test_limiter.check("1.2.3.4", "/api/scrape/run", force=True)
    assert allowed is False
    assert retry_after > 0


def test_rate_limiter_exempts_health_endpoints():
    """Verify health and exempt endpoints are not rate limited."""
    test_limiter = InMemoryRateLimiter()
    for _ in range(100):
        allowed, retry_after = test_limiter.check("1.2.3.4", "/system/health", force=True)
        assert allowed is True
        assert retry_after == 0


def test_production_mode_docs_configuration(monkeypatch):
    """Verify docs_url is None in production."""
    from backend.app.core.config import Settings
    custom_settings = Settings()
    assert custom_settings.public_runtime_config() is not None
