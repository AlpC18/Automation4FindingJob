"""Optional external error and trace reporting shared by API and workers."""

import threading
import time
from collections import defaultdict

from backend.app.core.config import settings

_initialized = False
_request_lock = threading.Lock()
_request_counts = defaultdict(int)
_request_latency_seconds = defaultdict(float)
_request_latency_buckets = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
_request_latency_bucket_counts = defaultdict(int)


class RequestMetricsMiddleware:
    """Collect low-cardinality HTTP request counters and latency histograms."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("path") == f"{settings.API_V1_PREFIX}/system/metrics":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status_code = 500

        async def record_status(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, record_status)
        finally:
            elapsed = max(0.0, time.perf_counter() - started)
            route = scope.get("route")
            path = getattr(route, "path", None) or "unmatched"
            key = (scope.get("method", "UNKNOWN"), path, status_code)
            with _request_lock:
                _request_counts[key] += 1
                _request_latency_seconds[key] += elapsed
                for bound in _request_latency_buckets:
                    if elapsed <= bound:
                        _request_latency_bucket_counts[(key, bound)] += 1


def render_request_metrics() -> str:
    lines = [
        "# HELP career_agent_http_requests_total Total completed HTTP requests.",
        "# TYPE career_agent_http_requests_total counter",
        "# HELP career_agent_http_request_duration_seconds Request latency distribution.",
        "# TYPE career_agent_http_request_duration_seconds histogram",
    ]
    with _request_lock:
        counts = dict(_request_counts)
        totals = dict(_request_latency_seconds)
        buckets = dict(_request_latency_bucket_counts)
    keys = sorted(counts)
    for method, route, status in keys:
        labels = f'method="{method}",route="{route}",status="{status}"'
        lines.append(f"career_agent_http_requests_total{{{labels}}} {counts[(method, route, status)]}")
        count = counts[(method, route, status)]
        total = totals.get((method, route, status), 0.0)
        for bound in _request_latency_buckets:
            lines.append(
                f'career_agent_http_request_duration_seconds_bucket{{{labels},le="{bound:g}"}} '
                f'{buckets.get(((method, route, status), bound), 0)}'
            )
        lines.append(f'career_agent_http_request_duration_seconds_bucket{{{labels},le="+Inf"}} {count}')
        lines.append(f"career_agent_http_request_duration_seconds_sum{{{labels}}} {total:.6f}")
        lines.append(f"career_agent_http_request_duration_seconds_count{{{labels}}} {count}")
    return "\n".join(lines) + "\n"

def initialize_error_monitoring() -> bool:
    global _initialized
    if _initialized:
        return True
    if not settings.SENTRY_DSN:
        return False
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=f"career-agent@{settings.VERSION}",
        traces_sample_rate=max(0.0, min(1.0, settings.SENTRY_TRACES_SAMPLE_RATE)),
        integrations=[StarletteIntegration(), FastApiIntegration()],
        send_default_pii=False,
    )
    _initialized = True
    return True
