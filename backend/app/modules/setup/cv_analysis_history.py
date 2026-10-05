"""Durable, privacy-preserving CV analysis history.

Only non-sensitive analysis metadata and the deterministic quality summary are
retained. The uploaded file, raw CV text, AI feedback, and generated draft are
intentionally never written here; the full result remains in the review screen
until the user decides what to apply to the profile.
"""

import json
import uuid
from typing import Any

from backend.app.core.database import get_db_connection
from backend.app.core.security import decrypt_secret, encrypt_secret


def record_analysis_run(
    *,
    filename: str,
    content_hash: str,
    page_count: int | None,
    character_count: int,
    ai_requested: bool,
    ai_used: bool,
    ai_provider: str | None,
    quality: dict[str, Any],
    analysis: dict[str, Any] | None,
) -> dict[str, Any]:
    run = {
        "id": uuid.uuid4().hex,
        "filename": filename[:255],
        "content_hash": content_hash,
        "page_count": page_count,
        "character_count": max(0, int(character_count)),
        "ai_requested": bool(ai_requested),
        "ai_used": bool(ai_used),
        "ai_provider": ai_provider[:80] if isinstance(ai_provider, str) else None,
        "quality": quality if isinstance(quality, dict) else {},
        # AI feedback can contain exact excerpts from a private resume. Keep it
        # in the in-memory review response only; never persist it in history.
        "analysis": {},
    }
    conn = get_db_connection()
    try:
        conn.cursor().execute(
            """INSERT INTO cv_analysis_runs
               (id, filename, content_hash, page_count, character_count,
                ai_requested, ai_used, ai_provider, quality_json, analysis_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run["id"], encrypt_secret(run["filename"]), run["content_hash"], run["page_count"],
                run["character_count"], int(run["ai_requested"]), int(run["ai_used"]),
                run["ai_provider"], json.dumps(run["quality"], ensure_ascii=False),
                json.dumps(run["analysis"], ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return run


def list_analysis_runs(limit: int = 20) -> list[dict[str, Any]]:
    conn = get_db_connection()
    try:
        rows = conn.cursor().execute(
            "SELECT * FROM cv_analysis_runs ORDER BY created_at DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            stored_filename = item.get("filename") or ""
            item["filename"] = decrypt_secret(stored_filename)
            if stored_filename and item["filename"] == stored_filename:
                conn.cursor().execute(
                    "UPDATE cv_analysis_runs SET filename = ? WHERE id = ?",
                    (encrypt_secret(stored_filename), item["id"]),
                )
            for key in ("quality_json", "analysis_json"):
                try:
                    item[key[:-5]] = json.loads(item.pop(key) or "{}")
                except (TypeError, ValueError):
                    item[key[:-5]] = {}
            item["ai_requested"] = bool(item.get("ai_requested"))
            item["ai_used"] = bool(item.get("ai_used"))
            result.append(item)
        conn.commit()
        return result
    finally:
        conn.close()
