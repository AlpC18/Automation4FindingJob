"""STAR interview prep, scraper health checks and the ranking state built on the seen-jobs tracker."""

from datetime import date, timedelta

import pytest

from backend.app.modules.interview.star_framework import star_framework
from backend.app.modules.rank import rank_state as rank_module
from backend.app.modules.scrape.portal_health import portal_health_checker
from backend.app.modules.scrape.seen_jobs_tracker import SeenJobsTracker


def test_questions_follow_the_signals_in_the_posting():
    questions = star_framework.generate_role_questions("Team Lead", "You will lead and mentor a team and design systems.")
    categories = [question["category"] for question in questions]

    assert {"leadership", "teamwork", "problem_solving", "impact"} <= set(categories)
    assert categories[0] in {"leadership", "teamwork", "problem_solving"}  # the most relevant come first
    assert "leadership" not in {q["category"] for q in star_framework.generate_role_questions("Analyst", "Write reports.")}
    assert set(star_framework.get_question_categories()) >= {"leadership", "failure"}


def test_star_stubs_come_from_real_achievements_only():
    profile = {
        "experience": [{"title": "Developer", "company": "Acme", "achievements": [
            "Led a team of four and reduced deploy time by 40 percent", "short",
        ]}],
        "skills": ["Python", "SQL"],
    }

    stubs = star_framework.extract_star_candidates(profile)

    assert [stub["source"] for stub in stubs] == ["CV — Developer @ Acme", "Skills section"]
    assert {"leadership", "impact"} <= set(stubs[0]["suggested_categories"])
    assert star_framework.extract_star_candidates({}) == []


def test_star_answers_are_scored_by_completeness_and_metrics():
    long_text = " ".join(["detail"] * 30)
    complete = star_framework.score_star_answer({
        "situation": long_text, "task": long_text, "action": long_text, "result": long_text + " cut costs by 30%",
    })
    partial = star_framework.score_star_answer({"situation": "Too short", "task": " ".join(["word"] * 12), "result": "It went well"})

    assert (complete["overall_score"], complete["is_complete"], complete["has_metrics"]) == (90.0, True, True)
    assert partial["component_scores"] == {"situation": 30, "task": 60, "action": 0, "result": 30}
    assert partial["is_complete"] is False and partial["has_metrics"] is False
    assert any("metrik" in line for line in partial["feedback"])


def _result(**overrides):
    return {"title": "Backend Developer", "company": "Acme", "url": "https://www.linkedin.com/jobs/1",
            "description": "Unique text", "posted_date": "2026-09-01", **overrides}


def test_healthy_scrape_output_is_reported_healthy():
    report = portal_health_checker.check_results_quality("linkedin", [_result(), _result(title="Data Engineer")])

    assert (report["status"], report["health_score"], report["issues"]) == ("healthy", 100, [])


def test_a_broken_parser_is_reported_as_degraded():
    broken = [_result(company="", title='<span class="x">Dev</span>', description="same", url="https://other.test/1") for _ in range(5)]

    report = portal_health_checker.check_results_quality("linkedin", broken)

    assert report["status"] == "degraded"
    assert len(report["issues"]) == 3  # no companies, markup in titles, identical descriptions
    assert any("linkedin" in warning for warning in report["warnings"])
    assert report["health_score"] == 0


def test_suspicious_dates_and_empty_runs_are_flagged():
    odd = portal_health_checker.check_results_quality("unknown-portal", [_result(posted_date="2030-01-01"), _result(company=None)])
    empty = portal_health_checker.check_results_quality("linkedin", [])

    assert odd["status"] == "warning" and any("future" in warning for warning in odd["warnings"])
    assert (empty["status"], empty["health_score"]) == ("no_results", 0)


def test_a_portal_that_suddenly_returns_nothing_is_noticed():
    assert "averaged 20" in portal_health_checker.check_yield_history("linkedin", 0, [20, 20, 20])
    assert portal_health_checker.check_yield_history("linkedin", 0, [1, 2]) is None
    assert portal_health_checker.check_yield_history("linkedin", 0, []) is None
    assert portal_health_checker.check_yield_history("linkedin", 3, [20]) is None


def test_full_health_report_combines_portals():
    report = portal_health_checker.full_health_report({"linkedin": [_result()], "upwork": []})

    assert report["overall_status"] == "issues_detected"
    assert report["portals"]["linkedin"]["status"] == "healthy"


@pytest.fixture
def ranking(monkeypatch, tmp_path):
    tracker = SeenJobsTracker(path=tmp_path / "seen.json")
    monkeypatch.setattr(rank_module, "seen_jobs_tracker", tracker)
    today = date.today()
    keys = {
        "ai": tracker.add("Acme", "AI Engineer", "https://a.test/1")[0],
        "web": tracker.add("Globex", "Web Developer", "https://g.test/2", extra={"deadline": (today + timedelta(days=2)).isoformat()})[0],
        "old": tracker.add("Initech", "Tester", "https://i.test/3", extra={"deadline": (today - timedelta(days=1)).isoformat()})[0],
    }
    tracker.mark_status(tracker.add("Hooli", "Skipped Role", "https://h.test/4")[0], "skipped")
    return tracker, keys


def test_only_new_jobs_are_ranking_candidates_and_focus_narrows_them(ranking):
    _, keys = ranking

    everything = rank_module.rank_state_manager.get_candidates()
    focused = rank_module.rank_state_manager.get_candidates(focus="ai engineer")

    assert everything["count"] == 3 and everything["skipped"]["skipped_status"] == 1
    assert [item["key"] for item in focused["candidates"]] == [keys["ai"]]
    assert rank_module.rank_state_manager.get_candidates(limit=1)["count"] == 1


def test_scores_are_written_back_and_summarised_by_tier(ranking):
    tracker, keys = ranking
    scores = [{"key": keys["ai"], "score": 88, "strengths": ["Python"]}, {"key": keys["web"], "score": 55},
              {"key": "unknown", "score": 10}, {"score": 5}]

    preview = rank_module.rank_state_manager.apply_scores(scores, dry_run=True)
    applied = rank_module.rank_state_manager.apply_scores(scores)
    summary = rank_module.rank_state_manager.get_ranking_summary()

    assert preview["applied_count"] == 3 and preview["error_count"] == 1
    assert applied["applied_keys"] == [keys["ai"], keys["web"]] and applied["error_count"] == 2
    assert (summary["high_match"]["count"], summary["medium_match"]["count"], summary["low_match"]["count"]) == (1, 1, 0)
    assert tracker.get_all()[keys["ai"]]["status"] == "ranked"
    assert rank_module.rank_state_manager.get_candidates()["skipped"]["already_ranked"] == 2
    assert rank_module.rank_state_manager.get_candidates(include_all=True)["count"] == 3


def test_sweep_reports_expired_and_closing_jobs_and_honours_exclusions(ranking):
    _, keys = ranking

    report = rank_module.rank_state_manager.sweep_and_report(dry_run=True)
    excluded = rank_module.rank_state_manager.sweep_and_report(dry_run=True, exclude_keys=[keys["old"], keys["web"]])

    assert [item["key"] for item in report["expired"]] == [keys["old"]]
    assert [item["key"] for item in report["closing_soon"]] == [keys["web"]]
    assert (excluded["expired_count"], excluded["closing_soon_count"]) == (0, 0)
