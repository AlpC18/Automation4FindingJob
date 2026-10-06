"""Defaults that keep the owner's accounts and other people's inboxes safe."""

import asyncio

from fastapi.testclient import TestClient

from backend.app.api.routers import application as application_router
from backend.app.core.config import settings
from backend.app.main import app
from backend.app.modules.outcome.oauth_mail_agent import oauth_mail_agent
from backend.app.modules.scrape.rate_limiter import account_health
from backend.app.modules.scrape.stealth_browser import stealth_worker

client = TestClient(app)


def test_linkedin_browser_automation_is_off_unless_enabled(monkeypatch):
    monkeypatch.setattr(settings, "LINKEDIN_AUTOMATION_ENABLED", False)

    result = asyncio.run(stealth_worker.execute_easy_apply_flow("https://www.linkedin.com/jobs/view/1", {}))

    assert result["status"] == "DISABLED"
    assert result["applied"] is False


def test_linkedin_browser_automation_stops_at_the_daily_quota(monkeypatch):
    monkeypatch.setattr(settings, "LINKEDIN_AUTOMATION_ENABLED", True)
    monkeypatch.setattr(account_health, "get_today_usage", lambda platform: 10_000)

    result = asyncio.run(stealth_worker.execute_easy_apply_flow("https://www.linkedin.com/jobs/view/1", {}))

    assert result["status"] == "QUOTA_EXHAUSTED"


def test_outreach_email_stops_at_the_daily_cap(monkeypatch):
    sent = []
    monkeypatch.setattr(
        application_router.email_finder, "send_smtp_outreach",
        lambda to, subject, body: sent.append(to) or {"status": "SENT", "message": "ok"},
    )
    monkeypatch.setitem(account_health.limits, "outreach", 2)
    used = account_health.get_today_usage("outreach")
    payload = {"to_email": "sam@acme.test", "subject": "Hello", "body_text": "Hi Sam"}

    statuses = [client.post("/api/decision-makers/send_email", json=payload).json()["status"] for _ in range(3)]

    allowed = max(0, 2 - used)
    assert statuses == ["SENT"] * allowed + ["DAILY_LIMIT_REACHED"] * (3 - allowed)
    assert len(sent) == allowed


def test_mail_connections_ask_for_read_access_only():
    scopes = " ".join(oauth_mail_agent.google_scopes + oauth_mail_agent.ms_scopes).lower()

    assert "send" not in scopes


def _sender(monkeypatch):
    sent = []
    monkeypatch.setattr(
        application_router.email_finder, "send_smtp_outreach",
        lambda to, subject, body: sent.append((to, body)) or {"status": "SENT", "message": "ok"},
    )
    monkeypatch.setitem(account_health.limits, "outreach", 10_000)
    return sent


def test_a_guessed_address_needs_an_explicit_confirmation(monkeypatch):
    sent = _sender(monkeypatch)
    payload = {"to_email": "guess@acme.test", "subject": "Hello", "body_text": "Hi", "address_is_guess": True}

    first = client.post("/api/decision-makers/send_email", json=payload).json()
    second = client.post("/api/decision-makers/send_email", json={**payload, "guess_confirmed": True}).json()

    assert (first["status"], second["status"]) == ("CONFIRMATION_REQUIRED", "SENT")
    assert len(sent) == 1


def test_outreach_carries_an_opt_out_line_and_respects_it(monkeypatch):
    sent = _sender(monkeypatch)
    payload = {"to_email": "Sam@Acme.test", "subject": "Hello", "body_text": "Hi Sam"}

    client.post("/api/decision-makers/send_email", json=payload)
    assert sent[0][1].startswith("Hi Sam\n\n") and "will not write again" in sent[0][1]

    assert client.post("/api/decision-makers/suppressions", json={"email": "not-an-address"}).status_code == 422
    assert "sam@acme.test" in client.post("/api/decision-makers/suppressions", json={"email": " sam@acme.test "}).json()["suppressed"]
    assert "sam@acme.test" in client.get("/api/decision-makers/suppressions").json()["suppressed"]
    assert client.post("/api/decision-makers/send_email", json=payload).json()["status"] == "SUPPRESSED"
    assert len(sent) == 1


def test_the_browser_is_not_launched_with_automation_hiding_flags():
    from backend.app.modules.scrape.stealth_browser import BROWSER_ARGS

    assert not any("AutomationControlled" in argument for argument in BROWSER_ARGS)


def test_old_outreach_contacts_are_dropped_after_the_retention_period(tmp_path):
    import json
    from datetime import datetime, timedelta

    from backend.app.modules.apply.cold_outreach import OUTREACH_RETENTION_DAYS, ColdOutreachEngine

    path = tmp_path / "outreach.json"
    old = (datetime.now() - timedelta(days=OUTREACH_RETENTION_DAYS + 1)).isoformat()
    path.write_text(json.dumps({"outreach_list": [
        {"id": "old", "manager_name": "Old Contact", "created_at": old},
        {"id": "new", "manager_name": "New Contact", "created_at": datetime.now().isoformat()},
    ]}), encoding="utf-8")

    assert [item["id"] for item in ColdOutreachEngine(data_path=path).list_outreach_campaigns()] == ["new"]


def test_postgres_queries_keep_literal_percent_signs():
    from backend.app.core.database import _PostgresCursor

    class Recorder:
        rowcount = 3

        def execute(self, query, params):
            self.query, self.params = query, params

    recorder = Recorder()
    cursor = _PostgresCursor(recorder)
    cursor.execute("SELECT 1 FROM form_memory WHERE ? LIKE '%' || question || '%' AND id = ?", ("q", 1))

    assert recorder.query == "SELECT 1 FROM form_memory WHERE %s LIKE '%%' || question || '%%' AND id = %s"
    assert recorder.params == ("q", 1) and cursor.rowcount == 3
