"""
Tier-1 Production Enhancements Test Suite
Covers:
1. LinkedIn Session Handshake & Cookie Persistence
2. Celery + Redis Task Queue Diagnostics & Dual-Mode Dispatcher
3. Official Google & Microsoft OAuth2 Mail Agent and Auto-Sync
"""

import asyncio
import threading
import time

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.modules.scrape.session_manager import linkedin_session_manager
from backend.app.tasks.dispatcher import task_dispatcher
from backend.app.modules.outcome.oauth_mail_agent import oauth_mail_agent
from backend.app.core.config import settings

client = TestClient(app)

# 1. LinkedIn Session Handshake Tests
def test_linkedin_session_handshake_flow():
    # Clear any previous test session
    linkedin_session_manager.clear_cookies()
    status_initial = linkedin_session_manager.get_status()
    assert status_initial["is_synced"] is False
    assert status_initial["has_li_at"] is False

    # Simulate cookie handshake from Chrome Extension
    cookies_payload = [
        {"name": "li_at", "value": "AQEDAAB001fake_token", "domain": ".linkedin.com", "path": "/", "secure": True},
        {"name": "JSESSIONID", "value": "ajax:998877", "domain": ".linkedin.com", "path": "/"}
    ]
    resp = client.post("/api/scrape/sync_linkedin_session", json={"cookies": cookies_payload})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["has_li_at"] is True
    assert data["cookie_count"] == 2

    # Verify status endpoint reflects active session
    status_resp = client.get("/api/scrape/linkedin_session_status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["is_synced"] is True
    assert status_data["has_li_at"] is True
    assert status_data["has_jsessionid"] is True
    assert status_data["cookie_count"] == 2

    # Clear session
    clear_resp = client.post("/api/scrape/clear_linkedin_session")
    assert clear_resp.status_code == 200
    assert clear_resp.json()["status"] == "SUCCESS"

# 2. Celery & Task Queue Diagnostics Tests
def test_task_queue_status_and_dispatch(monkeypatch, tmp_path):
    from backend.app.core.database import init_db
    from backend.app.modules.scrape.unified_scraper import unified_scraper
    from backend.app.tasks.dispatcher import task_dispatcher

    monkeypatch.setattr(settings, "DATA_PATH", tmp_path)
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'career_engine.db'}")
    monkeypatch.setattr(settings, "MULTI_TENANT_ENABLED", False)
    monkeypatch.setattr(task_dispatcher, "is_celery_active", lambda: False)
    monkeypatch.setattr(
        unified_scraper,
        "run_multi_platform_scrape",
        lambda **_kwargs: {"jobs": [], "total_scraped": 0},
    )
    init_db()

    resp = client.get("/api/tasks/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "mode" in data
    assert "redis_connected" in data
    assert "broker_url" in data
    assert set(data["durable_jobs"]) >= {"queued", "running", "retrying", "succeeded", "failed", "total"}
    assert data["mode"] in ("CELERY_REDIS", "ASYNC_LOCAL")

    # Dispatch scrape via dual-mode dispatcher
    dispatch_resp = client.post(
        "/api/tasks/dispatch_scrape",
        json={"keywords": "AI Engineer", "location": "Remote", "limit": 2}
    )
    assert dispatch_resp.status_code == 200
    dispatch_data = dispatch_resp.json()
    assert "dispatch_mode" in dispatch_data
    assert dispatch_data["dispatch_mode"] in ("CELERY_REDIS", "ASYNC_LOCAL")


def test_local_scrape_is_queued_and_runs_outside_the_request(monkeypatch, tmp_path):
    from backend.app.core.database import init_db
    from backend.app.modules.scrape.unified_scraper import unified_scraper
    from backend.app.tasks.dispatcher import task_dispatcher
    from backend.app.tasks.job_store import get_job

    monkeypatch.setattr(settings, "DATA_PATH", tmp_path)
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'career_engine.db'}")
    monkeypatch.setattr(settings, "MULTI_TENANT_ENABLED", False)
    monkeypatch.setattr(task_dispatcher, "is_celery_active", lambda: False)
    started = threading.Event()
    release = threading.Event()

    def slow_scrape(**_kwargs):
        started.set()
        assert release.wait(timeout=3), "test did not release the simulated scrape"
        return {"jobs": [{"id": "job-1"}], "total_scraped": 1, "newly_saved_count": 1}

    monkeypatch.setattr(unified_scraper, "run_multi_platform_scrape", slow_scrape)
    init_db()

    async def dispatch_and_wait_for_result():
        dispatched = await task_dispatcher.dispatch_scrape("Engineer", "Remote", limit=1)
        assert dispatched["status"] == "QUEUED"
        assert dispatched["dispatch_mode"] == "ASYNC_LOCAL"
        assert dispatched["job_id"]

        assert await asyncio.to_thread(started.wait, 2), "background scrape never started"
        in_progress = get_job(dispatched["job_id"])
        assert in_progress["status"] in {"queued", "running"}

        release.set()
        for _ in range(100):
            job = get_job(dispatched["job_id"])
            if job["status"] in {"succeeded", "failed"}:
                break
            await asyncio.sleep(0.01)

        completed = get_job(dispatched["job_id"])
        assert completed["status"] == "succeeded"
        assert '"newly_saved_count": 1' in completed["result_json"]

    try:
        asyncio.run(dispatch_and_wait_for_result())
    finally:
        release.set()

# 3. Google & Microsoft OAuth2 Mail Tests
def test_oauth_mail_flow(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_DATA_ENABLED", True)
    # Status check
    status_resp = client.get("/api/inbox/oauth/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert "google" in data
    assert "microsoft" in data
    assert "auth_url" in data["google"]
    assert "accounts.google.com" in data["google"]["auth_url"]
    assert "login.microsoftonline.com" in data["microsoft"]["auth_url"]

    # Connect Google (Instant/Simulated)
    connect_google = client.post("/api/inbox/oauth/connect_instant", json={"provider": "google"})
    assert connect_google.status_code == 200
    assert connect_google.json()["status"] == "SUCCESS"

    # Connect Microsoft
    connect_ms = client.post("/api/inbox/oauth/connect_instant", json={"provider": "microsoft"})
    assert connect_ms.status_code == 200
    assert connect_ms.json()["status"] == "SUCCESS"

    # Verify both connected
    status_after = client.get("/api/inbox/oauth/status").json()
    assert status_after["google"]["connected"] is True
    assert status_after["microsoft"]["connected"] is True

    # Trigger Email Sync
    sync_resp = client.post("/api/inbox/oauth/sync", json={})
    assert sync_resp.status_code == 200
    sync_data = sync_resp.json()
    assert sync_data["status"] == "SUCCESS"
    assert sync_data["synced_count"] >= 1

    # Disconnect
    disc_google = client.post("/api/inbox/oauth/disconnect", json={"provider": "google"})
    assert disc_google.status_code == 200
    disc_ms = client.post("/api/inbox/oauth/disconnect", json={"provider": "microsoft"})
    assert disc_ms.status_code == 200

# 4. Role Discovery & Work Style Search Tests
def test_role_discovery_and_custom_search(monkeypatch):
    from backend.app.core.config import settings

    monkeypatch.setattr(settings, "DEMO_DATA_ENABLED", True)
    monkeypatch.setattr(
        "backend.app.api.routers.setup.fetch_candidate_profile",
        lambda: {
            "full_name": "Test Candidate",
            "target_role": "Full Stack Engineer",
            "target_roles": ["Full Stack Engineer"],
            "years_of_experience": 4,
            "skills": ["Python", "FastAPI", "React", "Next.js", "TypeScript", "Docker"],
            "raw_cv_text": "Full stack engineer building production APIs and web applications.",
        },
    )
    from backend.app.modules.scrape.unified_scraper import unified_scraper
    monkeypatch.setattr(
        unified_scraper.scrapers["linkedin"],
        "fetch_jobs",
        lambda query, location=None: [{
            "id": "test-live-linkedin-job",
            "title": query,
            "company": "Test Employer",
            "platform": "linkedin",
            "url": "https://example.test/live-job",
            "location": "Istanbul",
            "remote_type": "Remote",
            "salary_range": "Not disclosed",
            "description": "A real source contract test listing with enough detail to be processed.",
            "posted_date": "Today",
        }],
    )
    monkeypatch.setattr(settings, "SCRAPER_PLATFORMS", "linkedin")
    # 1. Fetch discovered roles based on candidate CV
    resp = client.get("/api/setup/discovered_roles")
    assert resp.status_code == 200
    data = resp.json()
    assert "roles" in data
    assert len(data["roles"]) >= 3
    assert "location_presets" in data
    assert len(data["location_presets"]) == 4

    first_role = data["roles"][0]
    assert "title" in first_role
    assert "subtext" in first_role
    assert "reasons" in first_role
    assert "match_probability" not in first_role

    # 2. Trigger multi-role search with work style preference
    scrape_resp = client.post(
        "/api/scrape/run",
        json={
            "queries": [first_role["title"], "AI Systems Engineer"],
            "location_preference": "Istanbul",
            "remote_type": "Hybrid/Remote"
        }
    )
    assert scrape_resp.status_code == 200
    res_data = scrape_resp.json()
    assert res_data["dispatch_mode"] == "ASYNC_LOCAL"
    assert res_data["status"] == "QUEUED"
    assert res_data["job_id"]

    completed = None
    for _ in range(50):
        status_resp = client.get(f"/api/tasks/jobs/{res_data['job_id']}")
        assert status_resp.status_code == 200
        job = status_resp.json()["job"]
        if job["status"] in {"succeeded", "failed"}:
            completed = job
            break
        time.sleep(0.02)

    assert completed is not None
    assert completed["status"] == "succeeded"
    assert completed["result"]["count"] > 0
