"""The scanned job feed in the shape the report, digest and search screens read."""

from typing import Any, Dict

from backend.app.core.database import get_db_connection

UNTOUCHED_STATUSES = ("", "draft", "new")


def feed_jobs() -> Dict[str, Dict[str, Any]]:
    """Current postings plus every job already acted on, keyed by job id.

    These screens were written against the seen-jobs file, which scans no longer fill;
    the feed the jobs page shows lives in scraped_jobs.
    """
    conn = get_db_connection()
    try:
        rows = conn.cursor().execute(
            """SELECT id, title, company, location, description, url, platform, match_score, status,
                      first_seen_at, applied_at, submission_confirmed, deadline
               FROM scraped_jobs
               WHERE stale_at IS NULL OR LOWER(COALESCE(status, '')) NOT IN ('', 'draft', 'new')"""
        ).fetchall()
    finally:
        conn.close()
    return {row["id"]: _as_seen_job(dict(row)) for row in rows}


def _as_seen_job(row: Dict[str, Any]) -> Dict[str, Any]:
    status = str(row.get("status") or "").lower()
    if status in UNTOUCHED_STATUSES:
        status = "ranked" if row.get("match_score") else "new"
    return {
        "title": row.get("title") or "",
        "company": row.get("company") or "",
        "location": row.get("location") or "",
        "description": row.get("description") or "",
        "url": row.get("url") or "",
        "portal": row.get("platform") or "unknown",
        "match_score": float(row.get("match_score") or 0.0),
        "status": status,
        "first_seen": str(row.get("first_seen_at") or "").replace(" ", "T"),
        # A card moved to Applied by hand is not a sent application until it is confirmed.
        "applied_at": str(row.get("applied_at") or "").replace(" ", "T") if row.get("submission_confirmed") else "",
        "deadline": row.get("deadline") or "",
    }
