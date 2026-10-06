"""Health, backup and restore endpoints, and the background task runner in local mode."""

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.main import app
from backend.app.tasks import dispatcher as dispatcher_module
from backend.app.tasks.job_store import create_job, get_job, update_job

client = TestClient(app)


def test_health_and_runtime_config_expose_no_secrets():
    health = client.get("/api/system/health").json()
    runtime = client.get("/api/system/runtime-config").json()

    assert health["checks"]["database"]["status"] == "healthy"
    assert health["checks"]["redis"]["status"] in {"disabled", "healthy", "unhealthy"}
    assert "token" not in json.dumps(runtime).lower() or "api_auth_token" not in json.dumps(runtime).lower()
    assert client.get("/api/system/capabilities").status_code == 200
    assert client.get("/api/system/metrics").status_code == 200


@pytest.fixture
def workspace_db():
    path = Path(settings.DATA_PATH) / "career_engine.db"
    existed = path.exists()
    if not existed:
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE marker (value TEXT)")
        conn.execute("INSERT INTO marker VALUES ('kept')")
        conn.commit()
        conn.close()
    yield path
    if not existed:
        path.unlink(missing_ok=True)


def test_backup_download_is_a_readable_sqlite_snapshot(workspace_db, tmp_path):
    response = client.get("/api/system/backup")

    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert response.content.startswith(b"SQLite format 3")
    copy = tmp_path / "copy.sqlite3"
    copy.write_bytes(response.content)
    assert sqlite3.connect(copy).execute("SELECT count(*) FROM sqlite_master").fetchone()[0] >= 1


def test_restore_needs_confirmation_and_a_real_backup_file(monkeypatch):
    upload = {"backup_file": ("backup.sqlite3", b"this is not a database", "application/octet-stream")}

    assert client.post("/api/system/backup/restore", data={"confirmation": "yes"}, files=upload).status_code == 400
    assert client.post("/api/system/backup/restore", data={"confirmation": "RESTORE"}, files=upload).status_code == 400

    monkeypatch.setattr(settings, "BACKUP_MAX_SIZE_MB", 1, raising=False)
    too_big = {"backup_file": ("big.sqlite3", b"x" * (1024 * 1024 + 2), "application/octet-stream")}
    assert client.post("/api/system/backup/restore", data={"confirmation": "RESTORE"}, files=too_big).status_code == 413


@pytest.fixture
def dispatcher(monkeypatch):
    monkeypatch.setattr(dispatcher_module.TaskDispatcher, "is_celery_active", lambda self: False)
    return dispatcher_module.TaskDispatcher()


def _run_scan(monkeypatch, dispatcher, scrape, key):
    from backend.app.modules.scrape.unified_scraper import unified_scraper
    monkeypatch.setattr(unified_scraper, "run_multi_platform_scrape", scrape)

    async def scenario():
        first = await dispatcher.dispatch_scrape("backend", "Remote", idempotency_key=key, scrape_options={"platforms": ["kosovajob"]})
        await asyncio.gather(*dispatcher._local_tasks)
        return first, await dispatcher.dispatch_scrape("backend", "Remote", idempotency_key=key)

    return asyncio.run(scenario())


def test_a_local_scan_is_recorded_from_queue_to_result(monkeypatch, dispatcher):
    asked = {}

    def scrape(**options):
        asked.update(options)
        return {"jobs": [{}, {}], "total_scraped": 2, "newly_saved_count": 1, "scan_id": "scan-1"}

    first, repeat = _run_scan(monkeypatch, dispatcher, scrape, "task-test-ok")
    job = get_job(first["job_id"])

    assert (first["dispatch_mode"], first["status"]) == ("ASYNC_LOCAL", "QUEUED")
    assert asked["target_platforms"] == ["kosovajob"] and asked["location_preference"] == "Remote"
    assert job["status"] == "succeeded" and json.loads(job["result_json"])["count"] == 2
    assert repeat["job_id"] == first["job_id"] and "existing job" in repeat["message"]


def test_a_failed_scan_is_kept_as_failed_and_can_be_retried(monkeypatch, dispatcher):
    def broken(**options):
        raise RuntimeError("portal offline")

    first, _ = _run_scan(monkeypatch, dispatcher, broken, "task-test-fail")
    failed = get_job(first["job_id"])

    assert failed["status"] == "failed" and "portal offline" in failed["error_text"]

    from backend.app.modules.scrape.unified_scraper import unified_scraper
    monkeypatch.setattr(unified_scraper, "run_multi_platform_scrape", lambda **options: {"jobs": [], "total_scraped": 0})

    async def retry():
        result = await dispatcher.retry_scrape(first["job_id"])
        await asyncio.gather(*dispatcher._local_tasks)
        return result

    assert asyncio.run(retry())["status"] == "queued"
    assert get_job(first["job_id"])["status"] == "succeeded"


def test_only_failed_scan_jobs_can_be_retried(dispatcher):
    done, _ = create_job("scrape", {"keywords": "x"}, "task-test-done")
    update_job(done["id"], "succeeded", result={})
    other, _ = create_job("report", {}, "task-test-other")
    update_job(other["id"], "failed", error="boom")

    for job_id, message in ((done["id"], "Only failed"), (other["id"], "cannot be retried"), ("missing", "not found")):
        with pytest.raises(ValueError, match=message):
            asyncio.run(dispatcher.retry_scrape(job_id))


def test_queue_status_reports_local_mode_without_redis(monkeypatch, dispatcher):
    monkeypatch.setattr(dispatcher_module, "check_redis_connection", lambda: False)

    status = dispatcher.get_queue_status()

    assert (status["mode"], status["redis_connected"], status["worker_count"]) == ("ASYNC_LOCAL", False, 0)
    assert "durable_jobs" in status
    assert client.get("/api/tasks/jobs", params={"limit": 5}).status_code == 200
    assert client.get("/api/tasks/jobs/missing").status_code == 404
