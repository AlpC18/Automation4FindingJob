"""Runtime configuration and health interfaces for dynamic deployments."""

import re
import sqlite3
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, unquote, urlsplit

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from backend.app.core.capabilities import get_capabilities
from backend.app.core.config import production_config_issues, settings
from backend.app.core.backup_manager import restore_sqlite_workspace
from backend.app.core.database import get_db_connection, is_postgres_database
from backend.app.tasks.scheduler_daemon import scheduler_daemon
from backend.app.core.tenant import get_tenant_id
from backend.app.core.monitoring import render_request_metrics
from backend.app.modules.rank.salary_lookup import salary_data_path_for_tenant, salary_lookup

router = APIRouter()
RESTORE_CONFIRMATION = "RESTORE"


@router.get("/system/metrics", response_class=PlainTextResponse)
def system_metrics():
    """Prometheus-compatible request counters and latency histograms."""
    return PlainTextResponse(
        render_request_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )

# This allowlist is deliberately scoped to the tenant's career workspace DB.
# Shared identity/authentication tables are kept in a separate control DB and
# are never included in export or workspace-data deletion.
WORKSPACE_DATA_TABLES = (
    "cv_documents", "page_visits",
    "career_job_vectors", "application_attribution", "application_packages", "follow_up_queue",
    "inbox_messages", "telegram_events", "oauth_accounts", "linkedin_sessions",
    "seen_jobs", "account_activity_log", "cv_interview_questions", "form_memory",
    "candidate_projects", "candidate_profile", "scraped_jobs", "background_jobs",
    "job_source_runs", "job_source_settings", "saved_searches", "user_notifications",
    "profile_revisions", "llm_provider_credentials", "job_scan_runs",
    "job_source_snapshots", "company_feedback", "job_flags", "application_status_history", "cv_analysis_runs", "job_link_checks", "apify_usage_history",
)
SENSITIVE_EXPORT_COLUMNS = {"access_token", "refresh_token", "encrypted_token", "encrypted_api_key", "raw_cookie_preview", "encrypted_content"}


def _workspace_table_exists(cursor, table: str) -> bool:
    if is_postgres_database():
        cursor.execute("SELECT to_regclass(?) AS table_name", (table,))
        return cursor.fetchone()["table_name"] is not None
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,))
    return cursor.fetchone() is not None


def _is_sensitive_export_key(key: str) -> bool:
    key = key.lower()
    return (
        key in SENSITIVE_EXPORT_COLUMNS or key == "input_json" or "password" in key
        or "secret" in key or "error" in key or key.endswith("api_key") or key.endswith("token")
    )


def _redact_export_value(value, key: str = ""):
    if _is_sensitive_export_key(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {name: _redact_export_value(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [_redact_export_value(item) for item in value]
    if isinstance(value, str) and key.lower().endswith("_json"):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return value
        return json.dumps(_redact_export_value(parsed), ensure_ascii=False)
    return value


def _workspace_rows(cursor, table: str):
    cursor.execute(f"SELECT * FROM {table}")
    rows = []
    for row in cursor.fetchall():
        item = dict(row)
        rows.append({column: _redact_export_value(value, column) for column, value in item.items()})
    return rows


@router.get("/system/data/export")
def export_workspace_data():
    """Download user workspace records as JSON without exporting credentials."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        tables = {table: _workspace_rows(cursor, table) for table in WORKSPACE_DATA_TABLES if _workspace_table_exists(cursor, table)}
        salary_file = salary_data_path_for_tenant(get_tenant_id())
        salary_records = json.loads(salary_file.read_text(encoding="utf-8")) if salary_file.is_file() else None
        payload = {"format": "career-agent-workspace-export-v1", "secrets_redacted": True, "tables": tables, "salary_data": salary_records}
        return JSONResponse(
            content=jsonable_encoder(payload),
            headers={"Content-Disposition": 'attachment; filename="career-agent-data.json"', "Cache-Control": "no-store"},
        )
    finally:
        conn.close()


class DeleteWorkspaceDataRequest(BaseModel):
    confirmation: str


@router.delete("/system/data")
def delete_workspace_data(req: DeleteWorkspaceDataRequest):
    """Clear this tenant's career data while retaining its sign-in account."""
    if req.confirmation != "DELETE":
        raise HTTPException(status_code=400, detail="Verileri silmek için DELETE onayı gerekli.")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        deleted = {}
        # Clear dependents and application/job records first. Keep schema
        # metadata and shared auth tables intact so the user can sign in again.
        for table in WORKSPACE_DATA_TABLES:
            if not _workspace_table_exists(cursor, table):
                continue
            cursor.execute(f"SELECT COUNT(*) AS count FROM {table}")
            count = cursor.fetchone()["count"]
            cursor.execute(f"DELETE FROM {table}")
            deleted[table] = count
        conn.commit()
        salary_file = salary_data_path_for_tenant(get_tenant_id())
        if salary_file.is_file():
            salary_file.unlink()
            salary_lookup.reload_current()
            deleted["salary_data_file"] = 1
        return {"deleted_tables": deleted, "message": "Çalışma alanı verileri silindi. Giriş hesabı korunuyor."}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _database_check() -> Dict[str, Any]:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        return {"status": "healthy", "engine": "postgresql" if is_postgres_database() else "sqlite"}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)[:180]}


def _redis_check() -> Dict[str, Any]:
    if not settings.USE_CELERY:
        return {"status": "disabled", "url_configured": bool(settings.REDIS_URL)}
    try:
        import redis

        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        client.close()
        return {"status": "healthy"}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)[:180]}


@router.get("/system/runtime-config")
def get_runtime_config() -> Dict[str, Any]:
    """Expose non-secret deployment settings to the browser at runtime."""
    return settings.public_runtime_config()


@router.get("/system/capabilities")
async def get_system_capabilities(verify: bool = False) -> Dict[str, Any]:
    """Feature-level readiness: what works, what runs on a fallback, what is off."""
    return await get_capabilities(verify=verify)


@router.get("/system/health")
def get_system_health() -> Dict[str, Any]:
    database = _database_check()
    redis = _redis_check()
    daemon = scheduler_daemon.get_status()
    configuration_issues = production_config_issues()
    required_healthy = database["status"] == "healthy"
    if settings.USE_CELERY:
        required_healthy = required_healthy and redis["status"] == "healthy"
    return {
        "status": "healthy" if required_healthy and not configuration_issues else "degraded",
        "environment": settings.ENVIRONMENT,
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "checks": {"database": database, "redis": redis, "daemon": daemon, "configuration": {"status": "healthy" if not configuration_issues else "invalid", "issues": configuration_issues}},
        "runtime": settings.public_runtime_config(),
    }


@router.get("/system/backup")
def download_database_backup():
    """Download a consistent tenant-scoped backup; secrets never appear in argv or logs."""
    if is_postgres_database():
        pg_dump = shutil.which("pg_dump")
        if not pg_dump:
            raise HTTPException(status_code=503, detail="pg_dump is unavailable; enable provider-managed backups or install PostgreSQL client tools.")
        dsn = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)
        parsed = urlsplit(dsn)
        command = [pg_dump, "--no-password", "--format=custom", "--no-owner", "--no-privileges", "--host", parsed.hostname or "localhost", "--port", str(parsed.port or 5432), "--username", unquote(parsed.username or ""), "--dbname", unquote(parsed.path.lstrip("/")), "--file", "-"]
        tenant_id = get_tenant_id()
        if tenant_id:
            schema = f"tenant_{re.sub(r'[^a-zA-Z0-9]', '', tenant_id)}"
            command.extend(["--schema", schema])
        environment = os.environ.copy()
        environment["PGPASSWORD"] = unquote(parsed.password or "")
        sslmode = parse_qs(parsed.query).get("sslmode", [])
        if sslmode:
            environment["PGSSLMODE"] = sslmode[0]
        try:
            result = subprocess.run(command, capture_output=True, env=environment, timeout=300, check=False)
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=504, detail="PostgreSQL backup timed out.") from exc
        if result.returncode != 0:
            # pg_dump stderr can contain connection metadata; never echo it to a client.
            raise HTTPException(status_code=503, detail="PostgreSQL backup failed. Check database permissions and server logs.")
        scope = re.sub(r"[^a-zA-Z0-9]", "", tenant_id) if tenant_id else "database"
        return StreamingResponse(iter([result.stdout]), media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="career-agent-{scope}.dump"', "Cache-Control": "no-store"})
    tenant_id = get_tenant_id()
    if tenant_id:
        safe_tenant_id = re.sub(r"[^a-zA-Z0-9]", "", tenant_id)
        source_path = Path(settings.DATA_PATH) / "tenants" / f"{safe_tenant_id}.db"
        filename = f"career-agent-{safe_tenant_id}.sqlite3"
    else:
        source_path = Path(settings.DATA_PATH) / "career_engine.db"
        filename = "career-agent.sqlite3"
    if not source_path.is_file():
        raise HTTPException(status_code=404, detail="No database exists for this account yet.")
    with tempfile.TemporaryDirectory(prefix="career-agent-backup-") as temporary_dir:
        snapshot_path = Path(temporary_dir) / "snapshot.sqlite3"
        snapshot = sqlite3.connect(snapshot_path)
        try:
            with sqlite3.connect(f"{source_path.resolve().as_uri()}?mode=ro", uri=True) as source:
                source.backup(snapshot)
        finally:
            snapshot.close()
        data = snapshot_path.read_bytes()
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.sqlite3",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@router.post("/system/backup/restore")
async def restore_database_backup(
    confirmation: str = Form(...),
    backup_file: UploadFile = File(...),
):
    """Restore only the signed-in workspace after explicit confirmation."""
    if confirmation.strip() != RESTORE_CONFIRMATION:
        raise HTTPException(status_code=400, detail="Geri yüklemeyi onaylamak için RESTORE yazın.")
    if is_postgres_database():
        raise HTTPException(status_code=501, detail="PostgreSQL yedekleri uygulama içinden geri yüklenemez.")
    max_bytes = max(1, int(getattr(settings, "BACKUP_MAX_SIZE_MB", 512))) * 1024 * 1024
    contents = await backup_file.read(max_bytes + 1)
    await backup_file.close()
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail="Yedek dosyası izin verilen boyut sınırını aşıyor.")
    try:
        safety_backup = restore_sqlite_workspace(contents, get_tenant_id())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "restored", "safety_backup": safety_backup}


class PageVisitRequest(BaseModel):
    path: str


_PAGE_PATH = re.compile(r"^/[a-z0-9-]*$")


@router.post("/system/page-visit")
def record_page_visit(req: PageVisitRequest):
    """Count one opening of a screen. Only the first path segment is kept: no ids, no query strings."""
    page = "/" + req.path.split("?")[0].strip("/").split("/")[0].lower()
    if not _PAGE_PATH.match(page) or len(page) > 60:
        raise HTTPException(status_code=422, detail="Unknown page.")
    conn = get_db_connection()
    try:
        conn.cursor().execute(
            "INSERT INTO page_visits (path, day, visits) VALUES (?, ?, 1) ON CONFLICT(path, day) DO UPDATE SET visits = page_visits.visits + 1",
            (page, datetime.now(timezone.utc).date().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    return {"recorded": page}


@router.get("/system/page-usage")
def get_page_usage(days: int = 14):
    """Visits per screen over the last `days` days, most used first."""
    since = (datetime.now(timezone.utc).date() - timedelta(days=max(1, min(days, 365)))).isoformat()
    conn = get_db_connection()
    try:
        rows = conn.cursor().execute(
            "SELECT path, SUM(visits) AS visits, MAX(day) AS last_day FROM page_visits WHERE day >= ? GROUP BY path ORDER BY visits DESC, path",
            (since,),
        ).fetchall()
    finally:
        conn.close()
    return {"days": days, "pages": [dict(row) for row in rows]}

