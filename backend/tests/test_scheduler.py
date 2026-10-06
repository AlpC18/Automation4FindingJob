"""The background scheduler: what it runs, when, and how a failure surfaces."""

import asyncio
from contextlib import contextmanager
from datetime import time

import pytest

from backend.app.tasks import scheduler_daemon as module


@pytest.fixture
def daemon(monkeypatch):
    events = []

    async def broadcast(kind, payload):
        events.append(payload)

    monkeypatch.setattr(module.ws_manager, "broadcast", broadcast)
    monkeypatch.setattr(module, "_scheduled_tenants", lambda: [None])
    scheduler = module.AutonomousSchedulerDaemon()
    scheduler.events = events
    return scheduler


def test_schedule_times_fall_back_when_misconfigured(daemon):
    assert daemon._schedule_time("07:45", time(1, 0)) == time(7, 45)
    assert daemon._schedule_time("soon", time(1, 0)) == time(1, 0)
    assert daemon._schedule_time(None, time(1, 0)) == time(1, 0)
    assert daemon.get_status()["last_nightly_run"] == "Henüz çalışmadı"
    assert len(daemon.get_status()["active_schedules"]) == 3


def _stub_nightly(monkeypatch, scrape):
    from backend.app.api import profile as profile_module
    from backend.app.modules.rank import llm_reranker, scoring_engine

    async def review(profile):
        return {"reviewed": 2}

    monkeypatch.setattr(profile_module, "fetch_candidate_profile", lambda: {"target_role": "Backend Developer", "target_roles": ["API Engineer"]})
    monkeypatch.setattr(module.unified_scraper, "run_multi_platform_scrape", scrape)
    monkeypatch.setattr(scoring_engine, "rank_and_save_all_jobs", lambda profile: None)
    monkeypatch.setattr(llm_reranker, "review_top_jobs", review)
    monkeypatch.setattr(module, "run_enabled_saved_searches", lambda: [{"new_matches": 3}, {"new_matches": 1}])
    monkeypatch.setattr(module.seen_jobs_tracker, "sweep_expired", lambda dry_run: [{"key": "old"}])
    monkeypatch.setattr(module.seen_jobs_tracker, "get_closing_soon", lambda days: [])


def test_nightly_sweep_searches_the_candidates_own_roles_and_reports_totals(daemon, monkeypatch):
    asked = {}

    def scrape(queries, target_platforms):
        asked.update(queries=queries, platforms=target_platforms)
        return {"total_scraped": 12}

    _stub_nightly(monkeypatch, scrape)
    monkeypatch.setattr(module.settings, "NIGHTLY_SCAN_PLATFORMS", "kosovajob, remoteok")
    monkeypatch.setattr(module, "list_company_boards", lambda: ["https://jobs.lever.co/acme"])

    result = asyncio.run(daemon.trigger_nightly_sweep())

    assert asked == {"queries": ["Backend Developer", "API Engineer"], "platforms": ["kosovajob", "remoteok", "company_boards"]}
    assert result == {"status": "success", "scraped_count": 12, "saved_searches_run": 2, "saved_search_matches": 4,
                      "expired_cleaned": 1, "closing_soon_count": 0, "ai_reviewed": 2}
    assert daemon.events[-1]["action"] == "nightly_sweep_completed" and daemon.last_error is None


def test_a_failed_nightly_sweep_is_reported_not_hidden(daemon, monkeypatch):
    def scrape(queries, target_platforms):
        raise RuntimeError("portal offline")

    _stub_nightly(monkeypatch, scrape)

    result = asyncio.run(daemon.trigger_nightly_sweep())

    assert result == {"status": "error", "error": "portal offline"}
    assert daemon.events[-1]["action"] == "nightly_sweep_failed" and daemon.last_error == "portal offline"


def test_scan_sources_and_queries_have_sane_defaults(monkeypatch):
    monkeypatch.setattr(module.settings, "NIGHTLY_SCAN_PLATFORMS", " ")
    assert module.nightly_platforms() is None
    assert module.scan_queries({}) == [module.settings.DEFAULT_SCRAPE_QUERY]
    assert module.scan_queries({"target_role": "A", "target_roles": ["A", "B", "C", "D", "E"]}) == ["A", "B", "C", "D"]


def test_morning_prep_drafts_and_sends_one_summary(daemon, monkeypatch):
    from backend.app.modules.outcome import today as today_module
    sent = []

    async def prepare(min_score, max_daily_limit, auto_request_approval):
        return {"status": "success", "prepared_count": 2}

    async def notify(message):
        sent.append(message)

    monkeypatch.setattr(module.auto_apply_pipeline, "scan_and_prepare", prepare)
    monkeypatch.setattr(today_module, "get_today_actions", lambda: {"counts": {"inbox_reply": 1}, "actions": [{"kind": "new_matches", "count": 4}]})
    monkeypatch.setattr(module.telegram_dispatcher, "is_configured", lambda: True)
    monkeypatch.setattr(module.telegram_dispatcher, "send_notification", notify)

    result = asyncio.run(daemon.trigger_morning_prep())

    assert result["prepared_count"] == 2
    assert len(sent) == 1 and "2 ilan için başvuru taslağı hazırlandı" in sent[0] and "4 yeni yüksek uyumlu ilan" in sent[0]
    assert module.morning_message(0, {}) is None


def test_a_failed_morning_prep_is_reported(daemon, monkeypatch):
    async def prepare(**kwargs):
        raise RuntimeError("queue unreadable")

    monkeypatch.setattr(module.auto_apply_pipeline, "scan_and_prepare", prepare)

    result = asyncio.run(daemon.trigger_morning_prep())

    assert result == {"status": "error", "error": "queue unreadable", "prepared_count": 0}
    assert daemon.events[-1]["action"] == "morning_prep_failed"


def test_each_tenant_gets_its_own_run(daemon, monkeypatch):
    entered = []

    @contextmanager
    def use_tenant(tenant_id):
        entered.append(tenant_id)
        yield

    async def one_run():
        return {"status": "success"}

    monkeypatch.setattr(module, "_scheduled_tenants", lambda: ["t1", "t2"])
    monkeypatch.setattr(module, "use_tenant", use_tenant)
    monkeypatch.setattr(daemon, "_trigger_nightly_sweep_for_current_tenant", one_run)
    monkeypatch.setattr(daemon, "_trigger_morning_prep_for_current_tenant", one_run)

    nightly = asyncio.run(daemon.trigger_nightly_sweep())
    morning = asyncio.run(daemon.trigger_morning_prep())

    assert nightly["tenants_processed"] == morning["tenants_processed"] == 2
    assert entered == ["t1", "t2", "t1", "t2"]


def test_follow_up_reminders_count_notifications_and_survive_one_bad_tenant(daemon, monkeypatch):
    from backend.app.modules.outcome.follow_up_cadence import FollowUpCadenceEngine

    monkeypatch.setattr(FollowUpCadenceEngine, "emit_due_follow_up_notifications", staticmethod(lambda: 2))
    assert asyncio.run(daemon.trigger_follow_up_reminders()) == {"status": "success", "tenants_processed": 1, "notifications_created": 2}

    def broken():
        raise RuntimeError("db locked")

    monkeypatch.setattr(FollowUpCadenceEngine, "emit_due_follow_up_notifications", staticmethod(broken))
    result = asyncio.run(daemon.trigger_follow_up_reminders())

    assert result["notifications_created"] == 0 and daemon.last_error == "db locked"


def test_the_loop_runs_a_job_once_at_its_minute_and_stops_cleanly(daemon, monkeypatch):
    ran = []

    async def nightly():
        ran.append("nightly")
        daemon.last_nightly_run = daemon._now().isoformat()

    async def scenario():
        now = daemon._now()
        monkeypatch.setattr(module.settings, "SCHEDULER_NIGHTLY_TIME", f"{now.hour:02d}:{now.minute:02d}")
        monkeypatch.setattr(module.settings, "SCHEDULER_MORNING_TIME", f"{(now.hour + 5) % 24:02d}:00")
        monkeypatch.setattr(module.settings, "DAEMON_POLL_SECONDS", 5)
        monkeypatch.setattr(daemon, "trigger_nightly_sweep", nightly)
        started = await daemon.start_daemon()
        again = await daemon.start_daemon()
        await asyncio.sleep(0.05)
        stopped = await daemon.stop_daemon()
        return started, again, stopped, await daemon.stop_daemon()

    started, again, stopped, idle = asyncio.run(scenario())

    assert (started["status"], again["status"], stopped["status"], idle["status"]) == ("started", "already_running", "stopped", "not_running")
    assert ran == ["nightly"] and daemon.total_cycles == 1 and daemon.is_running is False
