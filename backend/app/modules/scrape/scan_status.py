"""Scan status summary and an evidence-based explanation for an empty job feed."""

import re
from typing import Any, Optional

from backend.app.core.config import settings
from backend.app.core.database import get_db_connection
from backend.app.modules.scrape.source_registry import get_source_health, list_scan_runs

FILTER_REASONS = ("location_mismatch", "work_mode_mismatch", "low_quality", "expired")

# ponytail: keyword matching on provider error text; switch to structured error
# codes from the scrapers if these messages start drifting.
_QUOTA = re.compile(r"quota|kota|limit|harcama|http 402|http 429", re.IGNORECASE)
_CREDENTIALS = re.compile(r"token|anahtar|actor id|not configured|configure apify|http 401|http 403", re.IGNORECASE)
_CONNECTION = re.compile(r"could not reach|timeout|timed out|connect|network|http 5\d\d", re.IGNORECASE)


def diagnose_empty_feed(last_run: Optional[dict[str, Any]], health: dict[str, dict[str, Any]], current_total: int) -> Optional[dict[str, Any]]:
    """Name the most likely cause of a zero-job feed from recorded scan facts only."""
    if current_total > 0:
        return None
    sources = list(health.values())
    if not last_run:
        cause = "no_scan" if any(item.get("configured") for item in sources) else "source_setup"
        return {"cause": cause, "error": None, "counts": {}}

    errors = [str(error) for error in last_run.get("errors") or []]
    error_text = " ".join(errors)
    raw = int(last_run.get("raw_fetched_count") or 0)
    eligible = int(last_run.get("total_scraped") or 0)
    filtered = {key: int((last_run.get("filtered") or {}).get(key) or 0) for key in FILTER_REASONS}
    counts = {"raw_fetched": raw, "eligible": eligible, "duplicates": int(last_run.get("duplicate_count") or 0), **filtered}
    first_error = errors[0] if errors else None

    # Listings were fetched but none survived: the search filters are the cause,
    # even when another source also failed.
    if raw > 0 and eligible == 0:
        dominant = max(FILTER_REASONS, key=lambda key: filtered[key])
        return {"cause": "filters", "dominant_filter": dominant if filtered[dominant] else None, "error": first_error, "counts": counts}
    if raw == 0 and errors:
        if _QUOTA.search(error_text) or any(item.get("quota_reached") for item in sources):
            cause = "quota"
        elif _CREDENTIALS.search(error_text) or any(item.get("token_needs_reentry") for item in sources):
            cause = "credentials"
        elif _CONNECTION.search(error_text):
            cause = "connection"
        else:
            cause = "source_error"
        return {"cause": cause, "error": first_error, "counts": counts}
    if raw == 0:
        return {"cause": "no_results", "error": None, "counts": counts}
    # Eligible listings exist but none are in the open feed: already known,
    # hidden, or moved into the application pipeline.
    return {"cause": "all_processed", "error": first_error, "counts": counts}


def _scheduler_status() -> dict[str, Any]:
    from backend.app.tasks.scheduler_daemon import scheduler_daemon

    conn = get_db_connection()
    try:
        row = conn.cursor().execute(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN enabled = 1 THEN 1 ELSE 0 END) AS enabled FROM saved_searches"
        ).fetchone()
    finally:
        conn.close()
    return {
        "is_running": bool(scheduler_daemon.is_running),
        "nightly_time": settings.SCHEDULER_NIGHTLY_TIME,
        "timezone": settings.SCHEDULER_TIMEZONE,
        "last_nightly_run": scheduler_daemon.last_nightly_run,
        "saved_searches": int(row["total"] or 0),
        "scheduled_searches": int(row["enabled"] or 0),
    }


def get_scan_status() -> dict[str, Any]:
    conn = get_db_connection()
    try:
        row = conn.cursor().execute(
            "SELECT COUNT(*) AS total FROM scraped_jobs WHERE stale_at IS NULL AND COALESCE(status, 'Draft') IN ('Draft', 'New', '')"
        ).fetchone()
    finally:
        conn.close()
    current_total = int(row["total"] or 0)
    runs = [run for run in list_scan_runs(5) if run.get("status") != "running"]
    last_run = runs[0] if runs else None
    health = get_source_health()
    return {
        "current_total": current_total,
        "last_run": last_run,
        "sources": health,
        "scheduler": _scheduler_status(),
        "empty_state": diagnose_empty_feed(last_run, health, current_total),
    }
