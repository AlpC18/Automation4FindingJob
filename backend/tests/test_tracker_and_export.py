"""The seen-jobs tracker keeps honest state, and a data export never carries secrets."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from backend.app.api.routers.system import _redact_export_value
from backend.app.main import app
from backend.app.modules.scrape.seen_jobs_tracker import SeenJobsTracker

client = TestClient(app)


def _tracker(tmp_path):
    return SeenJobsTracker(path=tmp_path / "seen_jobs.json")


def test_a_job_is_new_once_and_survives_a_restart(tmp_path):
    tracker = _tracker(tmp_path)

    key, is_new = tracker.add("Acme", "Backend Developer", "https://acme.test/1", portal="test")
    _, again = tracker.add("Acme", "Backend Developer", "https://acme.test/1", portal="test")

    assert (is_new, again) == (True, False)
    assert _tracker(tmp_path).get_all()[key]["status"] == "new"


def test_only_a_confirmed_submission_gets_an_applied_date(tmp_path):
    tracker = _tracker(tmp_path)
    key, _ = tracker.add("Acme", "Backend Developer", "https://acme.test/1")

    tracker.mark_applied(key)
    unconfirmed = dict(tracker.get_all()[key])
    tracker.mark_applied(key, confirmed=True)

    assert unconfirmed["submission_confirmed"] is False and "applied_at" not in unconfirmed
    assert tracker.get_all()[key]["submission_confirmed"] is True and "applied_at" in tracker.get_all()[key]
    assert tracker.mark_status("no-such-key", "interview") is False


def test_expired_and_closing_jobs_follow_the_deadline(tmp_path):
    tracker = _tracker(tmp_path)
    today = date.today()
    past, _ = tracker.add("Old Co", "Engineer", "https://old.test/1", extra={"deadline": (today - timedelta(days=2)).isoformat()})
    soon, _ = tracker.add("Soon Co", "Engineer", "https://soon.test/1", extra={"deadline": (today + timedelta(days=3)).isoformat()})
    tracker.add("Odd Co", "Engineer", "https://odd.test/1", extra={"deadline": "next week"})

    assert [item["key"] for item in tracker.sweep_expired(dry_run=True)] == [past]
    assert tracker.get_all()[past]["status"] == "new"  # a dry run changes nothing

    tracker.sweep_expired(dry_run=False)

    assert tracker.get_all()[past]["status"] == "expired"
    assert [item["key"] for item in tracker.get_closing_soon(days=7)] == [soon]


def test_export_redacts_secrets_at_every_depth():
    row = {
        "name": "Ada", "access_token": "abc", "smtp_password": "pw", "provider_api_key": "sk-1",
        "settings_json": '{"client_secret": "s3", "theme": "dark"}', "nested": {"refresh_token": "r", "note": "ok"},
    }

    redacted = {key: _redact_export_value(value, key) for key, value in row.items()}

    assert redacted["name"] == "Ada" and redacted["nested"]["note"] == "ok"
    assert all(secret not in str(redacted) for secret in ("abc", "pw", "sk-1", "s3", '"r"'))
    assert '"theme": "dark"' in redacted["settings_json"]


def test_export_endpoint_is_marked_redacted_and_not_cached():
    response = client.get("/api/system/data/export")

    assert response.status_code == 200
    assert response.json()["secrets_redacted"] is True
    assert response.headers["cache-control"] == "no-store"


def test_deleting_workspace_data_needs_the_typed_confirmation():
    response = client.request("DELETE", "/api/system/data", json={"confirmation": "yes"})

    assert response.status_code == 400


def test_page_usage_counts_screens_without_ids_or_queries():
    for path in ("/jobs", "/jobs?scope=current", "/jobs/123/details", "/kanban"):
        assert client.post("/api/system/page-visit", json={"path": path}).status_code == 200
    assert client.post("/api/system/page-visit", json={"path": "/../etc/passwd"}).status_code == 422
    assert client.post("/api/system/page-visit", json={"path": "/<script>"}).status_code == 422

    usage = {page["path"]: page["visits"] for page in client.get("/api/system/page-usage").json()["pages"]}

    assert usage["/jobs"] >= 3 and usage["/kanban"] >= 1
    assert all("?" not in path and path.count("/") == 1 for path in usage)
