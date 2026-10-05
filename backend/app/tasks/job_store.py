"""Durable per-tenant lifecycle records for background work."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from backend.app.core.database import get_db_connection


def _dict(row):
    return dict(row) if row is not None else None


def create_job(job_type: str, payload: dict, idempotency_key: Optional[str] = None) -> tuple[dict, bool]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if idempotency_key:
        cursor.execute("SELECT * FROM background_jobs WHERE idempotency_key = ?", (idempotency_key,))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return _dict(existing), False
    job_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO background_jobs(id, job_type, status, payload_json, idempotency_key) VALUES (?, ?, ?, ?, ?)",
        (job_id, job_type, "queued", json.dumps(payload), idempotency_key),
    )
    conn.commit()
    cursor.execute("SELECT * FROM background_jobs WHERE id = ?", (job_id,))
    job = _dict(cursor.fetchone())
    conn.close()
    return job, True


def update_job(job_id: str, status: str, *, result: Any = None, error: Optional[str] = None,
               celery_task_id: Optional[str] = None, increment_attempt: bool = False):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE background_jobs SET status = ?, result_json = COALESCE(?, result_json),
           error_text = ?, celery_task_id = COALESCE(?, celery_task_id),
           attempts = attempts + ?, updated_at = CURRENT_TIMESTAMP,
           started_at = CASE WHEN ? = 'running' AND started_at IS NULL THEN CURRENT_TIMESTAMP ELSE started_at END,
           completed_at = CASE WHEN ? IN ('succeeded', 'failed') THEN CURRENT_TIMESTAMP ELSE NULL END
           WHERE id = ?""",
        (status, json.dumps(result) if result is not None else None, error, celery_task_id,
         1 if increment_attempt else 0, status, status, job_id),
    )
    conn.commit()
    conn.close()


def get_job(job_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM background_jobs WHERE id = ?", (job_id,))
    job = _dict(cursor.fetchone())
    conn.close()
    return job


def list_jobs(limit: int = 50):
    conn = get_db_connection()
    cursor = conn.cursor()
    # A killed worker cannot update its durable lifecycle row. Surface these as
    # failed so the existing retry action can safely re-dispatch them.
    cursor.execute("SELECT id, updated_at FROM background_jobs WHERE status IN ('running', 'retrying')")
    stale_before = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=20)
    for row in cursor.fetchall():
        try:
            updated_at = datetime.fromisoformat(str(row["updated_at"]).replace("Z", "+00:00"))
            if updated_at.tzinfo:
                updated_at = updated_at.astimezone(timezone.utc).replace(tzinfo=None)
        except (TypeError, ValueError):
            continue
        if updated_at < stale_before:
            cursor.execute(
                "UPDATE background_jobs SET status = 'failed', error_text = ?, completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status IN ('running', 'retrying')",
                ("Worker heartbeat expired; the job can be retried.", row["id"]),
            )
    conn.commit()
    cursor.execute("SELECT * FROM background_jobs ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = [_dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_job_stats() -> dict[str, Any]:
    """Return durable queue counts after expiring abandoned worker heartbeats."""
    list_jobs(1)
    conn = get_db_connection()
    try:
        rows = conn.cursor().execute("SELECT status, COUNT(*) AS count FROM background_jobs GROUP BY status").fetchall()
        counts = {row["status"]: int(row["count"]) for row in rows}
        return {
            "queued": counts.get("queued", 0),
            "running": counts.get("running", 0),
            "retrying": counts.get("retrying", 0),
            "succeeded": counts.get("succeeded", 0),
            "failed": counts.get("failed", 0),
            "total": sum(counts.values()),
        }
    finally:
        conn.close()


def serialize_job(job: dict):
    if not job:
        return None
    job["payload"] = json.loads(job.pop("payload_json") or "{}")
    job["result"] = json.loads(job.pop("result_json") or "null")
    return job
