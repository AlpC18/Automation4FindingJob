"""The approval queue drafts and hands off; only the candidate's own confirmation counts as applied."""

import asyncio

import pytest

from backend.app.modules.apply import auto_apply_pipeline as module

JOBS = {
    "strong": {"company": "Acme", "title": "Backend Developer", "url": "https://acme.test/1", "match_score": 92},
    "good": {"company": "Globex", "title": "API Engineer", "url": "https://globex.test/2", "match_score": 80},
    "weak": {"company": "Initech", "title": "Support", "url": "https://initech.test/3", "match_score": 40},
    "done": {"company": "Hooli", "title": "Engineer", "url": "https://hooli.test/4", "match_score": 99, "status": "applied"},
}


@pytest.fixture
def queue(monkeypatch, tmp_path):
    marked = []

    async def draft(job_data, max_revisions=1):
        return {"cover_letter": f"Letter for {job_data['company']}"}

    async def broadcast(*args, **kwargs):
        return None

    monkeypatch.setattr(module.seen_jobs_tracker, "get_all", lambda: JOBS)
    monkeypatch.setattr(module.seen_jobs_tracker, "mark_status", lambda key, status, notes=None: marked.append((key, status)))
    monkeypatch.setattr(module.seen_jobs_tracker, "mark_applied", lambda key, notes=None, confirmed=False: marked.append((key, "applied")))
    monkeypatch.setattr(module.drafter_reviewer_pipeline, "run_pipeline", draft)
    monkeypatch.setattr(module.telegram_dispatcher, "is_configured", lambda: False)
    monkeypatch.setattr(module.ws_manager, "broadcast", broadcast)
    monkeypatch.setattr(module.ws_manager, "broadcast_sync", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module.kanban_manager, "confirm_submission_by_identity",
        lambda **kwargs: {"submission_confirmed": True},
    )
    pipeline = module.AutoApplyPipeline(queue_path=tmp_path / "queue.json")
    pipeline.marked = marked
    return pipeline


def test_scan_drafts_the_best_matches_up_to_the_daily_limit(queue):
    result = asyncio.run(queue.scan_and_prepare(min_score=75, max_daily_limit=1))

    assert [job["job_key"] for job in result["prepared_jobs"]] == ["strong"]
    assert queue.list_queue()[0]["status"] == "pending_approval"


def test_scan_skips_low_scores_and_jobs_already_applied_to(queue):
    result = asyncio.run(queue.scan_and_prepare(min_score=75, max_daily_limit=5))

    assert {job["job_key"] for job in result["prepared_jobs"]} == {"strong", "good"}
    assert asyncio.run(queue.scan_and_prepare(min_score=75, max_daily_limit=5))["prepared_count"] == 0


def test_nothing_counts_as_applied_until_the_candidate_confirms(queue):
    asyncio.run(queue.scan_and_prepare(min_score=90, max_daily_limit=5))

    assert asyncio.run(queue.submit_approved_application("strong"))["success"] is False
    assert queue.confirm_manual_submission("strong")["success"] is False

    assert asyncio.run(queue.approve_application("strong"))["submission_confirmed"] is False
    handoff = asyncio.run(queue.submit_approved_application("strong"))
    assert (handoff["handoff_required"], handoff["submission_confirmed"]) == (True, False)
    assert queue.list_queue()[0]["status"] == "awaiting_user_submission"
    assert queue.get_today_count() == 0

    assert queue.confirm_manual_submission("strong")["submission_confirmed"] is True
    assert queue.list_queue()[0]["status"] == "applied"
    assert queue.get_today_count() == 1
    assert ("strong", "applied") in queue.marked


def test_rejecting_a_draft_marks_the_job_skipped(queue):
    asyncio.run(queue.scan_and_prepare(min_score=90, max_daily_limit=5))

    assert queue.reject_application("strong", "not interested")["success"] is True
    assert ("strong", "skipped") in queue.marked
    assert queue.reject_application("missing")["success"] is False


def test_the_queue_survives_a_restart(queue, tmp_path):
    asyncio.run(queue.scan_and_prepare(min_score=90, max_daily_limit=5))

    reopened = module.AutoApplyPipeline(queue_path=tmp_path / "queue.json")

    assert [app["job_key"] for app in reopened.list_queue()] == ["strong"]
