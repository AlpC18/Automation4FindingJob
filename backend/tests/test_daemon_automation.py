"""Overnight automation searches for the candidate's own roles, scores results, and sends a useful morning summary."""

import asyncio

from backend.app.tasks import scheduler_daemon as sd


def test_scan_queries_come_from_the_profile_with_a_fallback(monkeypatch):
    assert sd.scan_queries({"target_role": "Junior Developer", "target_roles": ["Junior Developer", " Backend Developer ", ""]}) == [
        "Junior Developer", "Backend Developer",
    ]
    assert len(sd.scan_queries({"target_roles": [f"Role {i}" for i in range(9)]})) == sd.MAX_SCAN_QUERIES
    monkeypatch.setattr(sd.settings, "DEFAULT_SCRAPE_QUERY", "Developer")
    assert sd.scan_queries({}) == ["Developer"]


def test_nightly_sweep_scans_target_roles_then_ranks_and_reviews(monkeypatch):
    calls = []
    profile = {"target_roles": ["Junior Developer"]}
    monkeypatch.setattr("backend.app.api.profile.fetch_candidate_profile", lambda: profile)
    monkeypatch.setattr(sd.unified_scraper, "run_multi_platform_scrape", lambda **kwargs: calls.append(("scan", kwargs)) or {"total_scraped": 7})
    monkeypatch.setattr("backend.app.modules.rank.scoring_engine.rank_and_save_all_jobs", lambda p: calls.append(("rank", p)) or [])

    async def review(p):
        calls.append(("review", p))
        return {"reviewed": 3}

    async def broadcast(*args, **kwargs):
        return None

    monkeypatch.setattr("backend.app.modules.rank.llm_reranker.review_top_jobs", review)
    monkeypatch.setattr(sd, "run_enabled_saved_searches", lambda: [])
    monkeypatch.setattr(sd.seen_jobs_tracker, "sweep_expired", lambda dry_run=False: [])
    monkeypatch.setattr(sd.seen_jobs_tracker, "get_closing_soon", lambda days=3: [])
    monkeypatch.setattr(sd.ws_manager, "broadcast", broadcast)

    result = asyncio.run(sd.AutonomousSchedulerDaemon()._trigger_nightly_sweep_for_current_tenant())

    assert result["status"] == "success" and result["scraped_count"] == 7 and result["ai_reviewed"] == 3
    assert calls == [("scan", {"queries": ["Junior Developer"], "target_platforms": ["remote", "kosovajob", "techcareer"]}), ("rank", profile), ("review", profile)]
