"""The job-source and feed API: saved searches, boards, flags, sessions and the scan trigger."""

import pytest
from fastapi.testclient import TestClient

from backend.app.api.routers import scrape as routes
from backend.app.core.database import get_db_connection
from backend.app.main import app

client = TestClient(app)


@pytest.fixture
def job():
    conn = get_db_connection()
    conn.cursor().execute(
        "INSERT INTO scraped_jobs (id, title, company, platform, description, url, match_score) "
        "VALUES ('route-job', 'Backend Developer', 'Acme', 'test', 'Python APIs', 'https://acme.test/1', 77) "
        "ON CONFLICT(id) DO NOTHING"
    )
    conn.commit()
    conn.close()
    yield "route-job"
    conn = get_db_connection()
    conn.cursor().execute("DELETE FROM scraped_jobs WHERE id = 'route-job'")
    conn.cursor().execute("DELETE FROM job_flags WHERE job_id = 'route-job'")
    conn.commit()
    conn.close()


def test_saved_search_lifecycle():
    rejected = client.post("/api/scrape/saved-searches", json={"name": " ", "queries": ["  "]})
    unknown_ai = client.post("/api/scrape/saved-searches", json={"name": "X", "queries": ["dev"], "llm_provider": "skynet"})
    created = client.post("/api/scrape/saved-searches", json={
        "name": " Backend roles ", "queries": ["backend", "backend", " api "], "location": "Remote", "min_match_score": 60,
    }).json()

    assert (rejected.status_code, unknown_ai.status_code) == (422, 422)
    assert (created["name"], created["queries"], created["enabled"]) == ("Backend roles", ["backend", "api"], False)
    listed = client.get("/api/scrape/saved-searches").json()["searches"]
    assert any(search["id"] == created["id"] and search["queries"] == ["backend", "api"] for search in listed)

    assert client.patch(f"/api/scrape/saved-searches/{created['id']}", json={"enabled": True}).json() == {"id": created["id"], "enabled": True}
    assert client.patch("/api/scrape/saved-searches/missing", json={"enabled": True}).status_code == 404
    assert client.post("/api/scrape/saved-searches/missing/run").status_code == 404
    assert client.delete(f"/api/scrape/saved-searches/{created['id']}").json() == {"deleted": True}
    assert client.delete(f"/api/scrape/saved-searches/{created['id']}").status_code == 404


def test_company_boards_are_verified_before_they_are_saved(monkeypatch):
    monkeypatch.setattr(routes.company_board_job_sources, "verify", lambda provider, slug: 7)

    added = client.post("/api/scrape/company-boards", json={"board": "https://jobs.lever.co/routeprobe"})
    assert added.status_code == 200 and added.json()["open_jobs"] == 7
    assert added.json()["board"] == {"provider": "lever", "slug": "routeprobe", "origin": "saved"}
    assert any(board["slug"] == "routeprobe" for board in client.get("/api/scrape/company-boards").json()["boards"])

    def unreachable(provider, slug):
        raise RuntimeError("board did not answer")

    monkeypatch.setattr(routes.company_board_job_sources, "verify", unreachable)
    assert client.post("/api/scrape/company-boards", json={"board": "https://jobs.lever.co/other"}).status_code == 503
    assert client.post("/api/scrape/company-boards", json={"board": "not a board"}).status_code == 422

    remaining = client.delete("/api/scrape/company-boards/Lever/RouteProbe").json()["boards"]
    assert not any(board["slug"] == "routeprobe" for board in remaining)


def test_job_detail_flags_and_link_check(job):
    assert client.get("/api/scrape/jobs/missing").status_code == 404
    assert client.post("/api/scrape/jobs/missing/flags", json={"flag": "favorite", "enabled": True}).status_code == 404
    assert client.post("/api/scrape/jobs/missing/link-check").status_code == 404

    assert client.post(f"/api/scrape/jobs/{job}/flags", json={"flag": "favorite", "enabled": True, "note": "ask Sam"}).status_code == 200
    detail = client.get(f"/api/scrape/jobs/{job}").json()["job"]

    assert (detail["favorite"], detail["hidden"], detail["flag_note"]) == (True, False, "ask Sam")
    assert detail["ghost_reasons"] == [] and detail["ai_review"] is None and detail["source_link_check"] is None
    assert client.get(f"/api/scrape/jobs/{job}/flags").json()["favorite"] is True
    assert client.get(f"/api/scrape/jobs/{job}/link-check").json() == {"check": None}
    assert job in [item["id"] for item in client.get("/api/scrape/jobs", params={"flag": "favorite"}).json()["jobs"]]

    client.post(f"/api/scrape/jobs/{job}/flags", json={"flag": "hidden", "enabled": True})
    assert job not in [item["id"] for item in client.get("/api/scrape/jobs").json()["jobs"]]
    assert job in [item["id"] for item in client.get("/api/scrape/jobs", params={"flag": "hidden", "include_hidden": True}).json()["jobs"]]


def test_feed_filters_narrow_the_result(job):
    def ids(**params):
        return [item["id"] for item in client.get("/api/scrape/jobs", params=params).json()["jobs"]]

    assert job in ids(platform="test", location="", remote_type="all", min_match_score=70, sort="company")
    assert job in ids(status="Draft", sort="recent") and job in ids(include_history=False)
    assert job not in ids(min_match_score=90) and job not in ids(platform="linkedin") and job not in ids(status="Applied")
    assert job not in ids(location="Berlin") and job not in ids(remote_type="Onsite")
    assert client.get("/api/scrape/jobs", params={"sort": "random"}).status_code == 422


def test_status_pages_answer_without_any_configured_source():
    assert "runs" in client.get("/api/scrape/runs", params={"limit": 5}).json()
    assert client.get("/api/scrape/status").status_code == 200
    assert "linkedin" in client.get("/api/scrape/health").json()
    assert "sources" in client.get("/api/scrape/sources").json()
    assert client.get("/api/notifications").json()["notifications"] is not None
    assert client.post("/api/notifications/none/read").status_code == 404
    assert "snapshots" in client.get("/api/scrape/apify-quota/history").json()


def test_source_settings_reject_unknown_sources_and_report_connection_errors(monkeypatch):
    body = {"actor_id": "user/actor", "api_token": "", "input_json": "{}", "enabled": True}

    def failing(source, **overrides):
        raise RuntimeError("token rejected")

    monkeypatch.setattr(routes.apify_job_source, "test_connection", failing)

    assert client.put("/api/scrape/sources/not-a-source", json=body).status_code == 404
    assert client.post("/api/scrape/sources/not-a-source/test", json=body).status_code == 404
    assert client.post("/api/scrape/sources/linkedin/test", json=body).status_code == 422
    assert client.post("/api/scrape/sources/not-a-source/tokens/reveal").status_code == 404


def test_scan_trigger_passes_the_request_through(monkeypatch):
    seen = {}

    async def dispatch(**kwargs):
        seen.update(kwargs)
        return {"status": "QUEUED"}

    monkeypatch.setattr(routes.task_dispatcher, "dispatch_scrape", dispatch)

    response = client.post("/api/scrape/run", headers={"Idempotency-Key": "abc"}, json={
        "query": "backend", "queries": ["backend", "api"], "location_preference": "Remote", "platforms": ["kosovajob"],
    })

    assert response.json() == {"status": "QUEUED"}
    assert (seen["keywords"], seen["location"], seen["idempotency_key"]) == ("backend", "Remote", "abc")
    assert seen["scrape_options"]["platforms"] == ["kosovajob"] and seen["scrape_options"]["queries"] == ["backend", "api"]


def test_linkedin_session_can_be_saved_inspected_and_cleared():
    cookies = [{"name": "li_at", "value": "secret-cookie", "domain": ".linkedin.com", "path": "/"}]

    saved = client.post("/api/scrape/sync_linkedin_session", json={"cookies": cookies})
    status = client.get("/api/scrape/linkedin_session_status")
    cleared = client.post("/api/scrape/clear_linkedin_session")

    assert saved.status_code == status.status_code == cleared.status_code == 200
    assert "secret-cookie" not in saved.text + status.text
    assert client.get("/api/scrape/linkedin_session_status").json() != status.json()


def test_on_page_analysis_scores_a_posting_and_ranking_runs_without_ai(job):
    analysis = client.post("/api/scrape/analyze_on_the_fly", json={"title": "Python Developer", "company": "Acme", "description": "Python and FastAPI"})
    ranked = client.post("/api/rank/evaluate_all", params={"ai": False}).json()

    assert 0 <= analysis.json()["match_score"] <= 100
    assert ranked["status"] == "SUCCESS" and ranked["ai_review"] == {"status": "skipped", "reason": "not_requested"}
    assert client.post("/api/scrape/playwright_apply", json={"job_id": "missing"}).status_code == 404


def test_ranking_survives_a_job_with_empty_columns(job):
    from backend.app.modules.rank.scoring_engine import score_job_against_profile

    scored = score_job_against_profile(
        {"id": "x", "title": "Developer", "company": "Acme", "description": None, "location": None, "remote_type": None, "posted_date": None},
        {"skills": ["Python"]},
    )

    assert 0 <= scored["match_score"] <= 100
