"""Deep interface for user job curation and auditable application transitions."""

import uuid
from typing import Any, Optional

from backend.app.core.database import get_db_connection, in_chunks


VALID_FLAGS = {"favorite", "hidden"}


def get_job_flags(job_id: str) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        row = conn.cursor().execute(
            "SELECT job_id, favorite, hidden, note, updated_at FROM job_flags WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if not row:
            return {"job_id": job_id, "favorite": False, "hidden": False, "note": "", "updated_at": None}
        item = dict(row)
        item["favorite"] = bool(item.get("favorite"))
        item["hidden"] = bool(item.get("hidden"))
        return item
    finally:
        conn.close()


def get_job_flags_for_ids(job_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not job_ids:
        return {}
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        rows = []
        for chunk in in_chunks(job_ids):
            placeholders = ",".join("?" for _ in chunk)
            rows.extend(cursor.execute(
                f"SELECT job_id, favorite, hidden, note, updated_at FROM job_flags WHERE job_id IN ({placeholders})",
                chunk,
            ).fetchall())
        result = {}
        for row in rows:
            item = dict(row)
            item["favorite"] = bool(item.get("favorite"))
            item["hidden"] = bool(item.get("hidden"))
            result[item["job_id"]] = item
        return result
    finally:
        conn.close()


def set_job_flag(job_id: str, flag: str, enabled: bool, note: str = "") -> dict[str, Any]:
    if flag not in VALID_FLAGS:
        raise ValueError(f"Geçersiz ilan işareti: {flag}")
    conn = get_db_connection()
    try:
        exists = conn.cursor().execute("SELECT id FROM scraped_jobs WHERE id = ?", (job_id,)).fetchone()
        if not exists:
            raise ValueError("Job not found")
        conn.cursor().execute(
            """INSERT INTO job_flags(job_id, favorite, hidden, note, updated_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(job_id) DO UPDATE SET
               favorite = CASE WHEN ? = 'favorite' THEN excluded.favorite ELSE job_flags.favorite END,
               hidden = CASE WHEN ? = 'hidden' THEN excluded.hidden ELSE job_flags.hidden END,
               note = CASE WHEN ? <> '' THEN excluded.note ELSE job_flags.note END,
               updated_at = CURRENT_TIMESTAMP""",
            (job_id, int(enabled) if flag == "favorite" else 0, int(enabled) if flag == "hidden" else 0,
             note[:1000], flag, flag, note),
        )
        conn.commit()
    finally:
        conn.close()
    return get_job_flags(job_id)


def record_status_transition(
    job_id: str,
    from_status: Optional[str],
    to_status: str,
    *,
    source: str = "kanban",
    note: str = "",
) -> dict[str, Any]:
    transition = {
        "id": uuid.uuid4().hex,
        "job_id": job_id,
        "from_status": from_status or "Draft",
        "to_status": to_status,
        "source": source,
        "note": note[:1000],
    }
    conn = get_db_connection()
    try:
        conn.cursor().execute(
            """INSERT INTO application_status_history
               (id, job_id, from_status, to_status, source, note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            tuple(transition.values()),
        )
        conn.commit()
    finally:
        conn.close()
    return transition


def list_status_history(job_id: str, limit: int = 50) -> list[dict[str, Any]]:
    conn = get_db_connection()
    try:
        rows = conn.cursor().execute(
            "SELECT * FROM application_status_history WHERE job_id = ? ORDER BY created_at DESC LIMIT ?",
            (job_id, max(1, min(limit, 200))),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
