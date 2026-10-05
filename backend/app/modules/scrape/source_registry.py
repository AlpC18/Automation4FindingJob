"""Tenant-scoped source configuration and compact provider health history."""

import json
import time
import uuid
from typing import Any, Optional

from cryptography.fernet import InvalidToken

from backend.app.core.config import settings
from backend.app.core.database import get_db_connection
from backend.app.core.security import decrypt_secret, encrypt_secret

ACTOR_SOURCES = (
    "linkedin", "upwork", "kosovajob",
    "fiverr", "freelancer", "toptal",
    "gjirafawork", "kariyernet",
    "indeed", "glassdoor", "wellfound",
)
ALL_SOURCES = (*ACTOR_SOURCES, "remote", "techcareer")
# Work without credentials; an Apify Actor is optional for these.
KEY_FREE_SOURCES = ("remote", "kosovajob", "techcareer")


def get_source_config(source: str) -> dict[str, Any]:
    if source not in ACTOR_SOURCES:
        return {"actor_id": "", "api_token": "", "api_tokens": [], "input_json": "{}", "enabled": True, "has_custom_config": False, "token_needs_reentry": False}
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM job_source_settings WHERE source = ?", (source,))
        row = cursor.fetchone()
        if not row:
            return {"actor_id": "", "api_token": "", "api_tokens": [], "input_json": "{}", "enabled": True, "has_custom_config": False, "token_needs_reentry": False}
        token_needs_reentry = False
        try:
            decrypted = decrypt_secret(row["encrypted_token"])
        except (InvalidToken, RuntimeError, UnicodeDecodeError):
            # Keep a stale encryption key from taking down scans or health checks.
            # The original token cannot be recovered; the owner must save it again.
            decrypted = ""
            token_needs_reentry = True
        try:
            parsed_tokens = json.loads(decrypted)
            api_tokens = [str(token).strip() for token in parsed_tokens if str(token).strip()] if isinstance(parsed_tokens, list) else [decrypted] if decrypted else []
        except (TypeError, json.JSONDecodeError):
            # Existing installs stored a single token as a plain encrypted string.
            api_tokens = [decrypted] if decrypted else []
        return {
            "actor_id": row["actor_id"],
            "api_token": api_tokens[0] if api_tokens else "",
            "api_tokens": api_tokens,
            "input_json": row["input_json"],
            "enabled": bool(row["enabled"]),
            "has_custom_config": True,
            "token_needs_reentry": token_needs_reentry,
        }
    finally:
        conn.close()


def apify_tokens(source: str) -> list[str]:
    """A source's own Apify tokens, else the shared ones: APIFY_API_TOKEN, then tokens saved for another source."""
    own = get_source_config(source)["api_tokens"]
    if own:
        return own
    if settings.APIFY_API_TOKEN.strip():
        return [settings.APIFY_API_TOKEN.strip()]
    for other in ACTOR_SOURCES:
        tokens = get_source_config(other)["api_tokens"]
        if tokens:
            return tokens
    return []


def save_source_config(source: str, *, actor_id: str, api_token: Optional[str], input_json: str, enabled: bool):
    if source not in ACTOR_SOURCES:
        raise ValueError("This provider does not accept an Actor configuration.")
    try:
        parsed_input = json.loads(input_json or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("Actor input must be valid JSON.") from exc
    if not isinstance(parsed_input, dict):
        raise ValueError("Actor input must be a JSON object.")
    existing = get_source_config(source)
    if api_token is None:
        encrypted_token = encrypt_secret(json.dumps(existing["api_tokens"])) if existing["api_tokens"] else ""
    else:
        tokens = list(dict.fromkeys(part.strip() for part in api_token.replace(",", "\n").splitlines() if part.strip()))
        encrypted_token = encrypt_secret(json.dumps(tokens)) if tokens else ""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO job_source_settings(source, actor_id, encrypted_token, input_json, enabled, updated_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(source) DO UPDATE SET actor_id=excluded.actor_id,
               encrypted_token=excluded.encrypted_token, input_json=excluded.input_json,
               enabled=excluded.enabled, updated_at=CURRENT_TIMESTAMP""",
            (source, actor_id.strip(), encrypted_token, json.dumps(parsed_input), int(enabled)),
        )
        conn.commit()
    finally:
        conn.close()


def delete_source_config(source: str):
    if source not in ACTOR_SOURCES:
        raise ValueError("This provider does not accept an Actor configuration.")
    conn = get_db_connection()
    try:
        conn.cursor().execute("DELETE FROM job_source_settings WHERE source = ?", (source,))
        conn.commit()
    finally:
        conn.close()


def record_source_run(source: str, status: str, jobs_count: int, error: Optional[str], latency_ms: float):
    conn = get_db_connection()
    try:
        conn.cursor().execute(
            "INSERT INTO job_source_runs(id, source, status, jobs_count, error_text, latency_ms, started_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, source, status, jobs_count, (error or "")[:500] or None, max(0, latency_ms), time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def create_scan_run(queries: list[str], platforms: list[str]) -> str:
    scan_id = uuid.uuid4().hex
    conn = get_db_connection()
    try:
        conn.cursor().execute(
            "INSERT INTO job_scan_runs(id, query_json, platforms_json) VALUES (?, ?, ?)",
            (scan_id, json.dumps(queries, ensure_ascii=False), json.dumps(platforms, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()
    return scan_id


def finish_scan_run(
    scan_id: str,
    *,
    status: str,
    total_scraped: int,
    newly_saved_count: int,
    removed_count: int,
    errors: list[str],
    raw_fetched_count: int = 0,
    filtered_count: int = 0,
    duplicate_count: int = 0,
    filtered: Optional[dict[str, int]] = None,
):
    conn = get_db_connection()
    try:
        conn.cursor().execute(
            """UPDATE job_scan_runs SET status = ?, total_scraped = ?, newly_saved_count = ?,
               removed_count = ?, errors_json = ?, raw_fetched_count = ?, filtered_count = ?,
               duplicate_count = ?, filtered_json = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (status, total_scraped, newly_saved_count, removed_count, json.dumps(errors, ensure_ascii=False),
             raw_fetched_count, filtered_count, duplicate_count, json.dumps(filtered or {}), scan_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_scan_runs(limit: int = 20) -> list[dict[str, Any]]:
    conn = get_db_connection()
    try:
        rows = conn.cursor()
        rows.execute("SELECT * FROM job_scan_runs ORDER BY started_at DESC LIMIT ?", (max(1, min(limit, 100)),))
        result = []
        for row in rows.fetchall():
            item = dict(row)
            item["queries"] = json.loads(item.pop("query_json") or "[]")
            item["platforms"] = json.loads(item.pop("platforms_json") or "[]")
            item["errors"] = json.loads(item.pop("errors_json") or "[]")
            item["filtered"] = json.loads(item.pop("filtered_json", None) or "{}")
            result.append(item)
        return result
    finally:
        conn.close()


def get_source_health() -> dict[str, dict[str, Any]]:
    health = {}
    cutoff = time.time() - 7 * 86400
    today_start = time.time() - (time.time() % 86400)
    for source in ALL_SOURCES:
        config = get_source_config(source)
        global_actor = getattr(settings, f"APIFY_ACTOR_{source.upper()}", "").strip() if source in ACTOR_SOURCES else ""
        actor_id = config["actor_id"] or global_actor
        has_token = bool(apify_tokens(source)) if source in ACTOR_SOURCES else False
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM job_source_runs WHERE source = ? ORDER BY started_at DESC LIMIT 1", (source,))
            last = cursor.fetchone()
            cursor.execute(
                "SELECT COUNT(*) AS total, SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successes FROM job_source_runs WHERE source = ? AND started_at >= ?",
                (source, cutoff),
            )
            totals = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) AS total FROM job_source_runs WHERE source = ? AND started_at >= ?", (source, today_start))
            today_runs = cursor.fetchone()
        finally:
            conn.close()
        ready = (source in KEY_FREE_SOURCES and config["enabled"]) or bool(actor_id and has_token and config["enabled"])
        missing = []
        if source in ACTOR_SOURCES and source not in KEY_FREE_SOURCES:
            if not actor_id:
                missing.append("actor_id")
            if not has_token:
                missing.append("api_token")
            if config["token_needs_reentry"]:
                missing.append("token_reentry")
            if not config["enabled"]:
                missing.append("disabled")
        daily_limit = settings.APIFY_MAX_ACTOR_RUNS_PER_DAY if source in ACTOR_SOURCES else None
        runs_today_count = today_runs["total"] or 0
        health[source] = {
            "source": source,
            "configured": ready,
            "requires_key": source in ACTOR_SOURCES,
            "missing": missing,
            "quota_reached": bool(daily_limit and runs_today_count >= daily_limit),
            "enabled": config["enabled"],
            "actor_id": actor_id if source in ACTOR_SOURCES else None,
            "token_configured": has_token if source in ACTOR_SOURCES else None,
            "token_needs_reentry": config["token_needs_reentry"] if source in ACTOR_SOURCES else False,
            "status": last["status"] if last else ("ready" if ready else "needs_configuration"),
            "last_error": last["error_text"] if last else None,
            "last_run_at": last["started_at"] if last else None,
            "last_jobs_count": last["jobs_count"] if last else 0,
            "last_latency_ms": last["latency_ms"] if last else None,
            "runs_7d": totals["total"] or 0,
            "successes_7d": totals["successes"] or 0,
            "runs_today": runs_today_count,
            "daily_run_limit": daily_limit,
            "max_items_per_run": settings.APIFY_MAX_ITEMS_PER_RUN if source in ACTOR_SOURCES else None,
            "max_charge_per_run_usd": settings.APIFY_MAX_TOTAL_CHARGE_USD if source in ACTOR_SOURCES else None,
        }
    return health


def public_source_config(source: str) -> dict[str, Any]:
    config = get_source_config(source)
    return {
        "source": source,
        "actor_id": config["actor_id"] or getattr(settings, f"APIFY_ACTOR_{source.upper()}", ""),
        "input_json": config["input_json"] if config["has_custom_config"] else getattr(settings, f"APIFY_INPUT_{source.upper()}", "{}"),
        "enabled": config["enabled"],
        "token_configured": bool(apify_tokens(source)),
        "token_count": len(apify_tokens(source)),
        "token_needs_reentry": config["token_needs_reentry"],
    }


def list_company_boards() -> list[dict[str, str]]:
    """Company career boards to scan: COMPANY_BOARDS from the environment plus those saved in the app."""
    from backend.app.modules.scrape.public_feeds import parse_company_boards

    boards = [{"provider": provider, "slug": slug, "origin": "env"} for provider, slug in parse_company_boards(settings.COMPANY_BOARDS)]
    known = {(board["provider"], board["slug"]) for board in boards}
    conn = get_db_connection()
    try:
        rows = conn.cursor().execute("SELECT provider, slug FROM company_boards ORDER BY provider, slug").fetchall()
    finally:
        conn.close()
    boards += [{"provider": row["provider"], "slug": row["slug"], "origin": "saved"} for row in rows if (row["provider"], row["slug"]) not in known]
    return boards


def save_company_board(provider: str, slug: str) -> None:
    conn = get_db_connection()
    try:
        conn.cursor().execute(
            "INSERT INTO company_boards(provider, slug) VALUES (?, ?) ON CONFLICT(provider, slug) DO NOTHING", (provider, slug),
        )
        conn.commit()
    finally:
        conn.close()


def delete_company_board(provider: str, slug: str) -> None:
    conn = get_db_connection()
    try:
        conn.cursor().execute("DELETE FROM company_boards WHERE provider = ? AND slug = ?", (provider, slug))
        conn.commit()
    finally:
        conn.close()
