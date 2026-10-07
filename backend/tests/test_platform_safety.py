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


def test_mail_connections_ask_for_read_access_only():
    scopes = " ".join(oauth_mail_agent.google_scopes + oauth_mail_agent.ms_scopes).lower()

    assert "send" not in scopes


def test_the_browser_is_not_launched_with_automation_hiding_flags():
    from backend.app.modules.scrape.stealth_browser import BROWSER_ARGS

    assert not any("AutomationControlled" in argument for argument in BROWSER_ARGS)


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
