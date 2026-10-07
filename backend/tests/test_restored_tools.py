"""Interview practice, offer review, salary records and reports: the tools brought back after the simplification."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api.routers.intelligence import SalaryAddRequest
from backend.app.core.llm_client import LLMUnavailable
from backend.app.core import llm_client as llm_module
from backend.app.core.tenant import reset_tenant_id, set_tenant_id
from backend.app.main import app
from backend.app.modules.interview.offer_negotiator import offer_negotiator_engine
from backend.app.modules.interview.star_framework import star_framework
from backend.app.modules.outcome import html_report as report_module
from backend.app.modules.outcome import weekly_digest
from backend.app.modules.rank.salary_benchmark import calculate_salary_benchmark
from backend.app.modules.rank.salary_lookup import SalaryLookup, assess_salary_evidence

client = TestClient(app)


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


def test_voice_interview_coach_metrics():
    from backend.app.modules.interview.voice_coach import voice_coach
    sample_answer = (
        "When I was at my previous company, we needed to optimize database latency. "
        "I built a Redis caching layer and optimized query indexes. "
        "This resulted in a 40% latency reduction and improved throughput significantly, like you know."
    )
    metrics = voice_coach.evaluate_vocal_performance(
        question="Tell me about a technical challenge you solved.",
        transcript=sample_answer,
        duration_seconds=20.0
    )
    assert metrics["wpm"] > 50
    assert metrics["total_fillers"] >= 1
    assert metrics["star_breakdown"]["situation"] is True
    assert metrics["star_breakdown"]["result"] is True
    assert metrics["overall_score"] >= 60


def test_legacy_counter_offer_contract_is_available():
    response = client.post(
        "/api/interview/counter_offer",
        json={
            "company_name": "Acme",
            "role_title": "Backend Engineer",
            "initial_offer": "$100,000",
            "market_benchmark": "$110,000",
            "target_amount": "$115,000",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["recommendation"]["base_salary"] == 100000
    assert payload["counter_letter"]["status"] == "use_counter_letter_endpoint"


def test_counter_offer_letter_fails_without_a_provider(monkeypatch):
    monkeypatch.setattr(llm_module.llm_client, "get_effective_provider", lambda requested=None: "none")

    with pytest.raises(LLMUnavailable):
        asyncio.run(offer_negotiator_engine.generate_counter_offer_letter(
            company="Acme", title="Backend Developer", offered_base=50000, target_base=60000,
        ))


def test_salary_evidence_score_is_metadata_completeness_not_verification():
    empty = assess_salary_evidence({})
    assert empty["score"] == 0
    assert empty["level"] == "limited_evidence"
    assert empty["independently_verified"] is False

    documented = assess_salary_evidence({
        "source_name": "Company compensation page",
        "source_url": "https://example.test/salary",
        "as_of": "2026-01-15",
        "sample_size": 12,
        "source_count": 2,
    })
    assert documented["score"] == 100
    assert documented["level"] == "well_documented"
    assert documented["independently_verified"] is False


def test_salary_lookup_is_isolated_per_tenant(tmp_path):
    lookup = SalaryLookup(tmp_path / "salary_data.json")
    tenant_token = set_tenant_id("salary-user-a")
    try:
        lookup.add_company("Example Co", salary_median=100000, source_name="User report")
        lookup.data_path.unlink()
        lookup.reload_current()
        assert lookup.stats()["total_companies"] == 0
    finally:
        reset_tenant_id(tenant_token)

    tenant_token = set_tenant_id("salary-user-b")
    try:
        assert lookup.search("Example Co") == []
    finally:
        reset_tenant_id(tenant_token)


def test_salary_api_validates_provenance_fields_and_benchmarks_are_labeled_estimates():
    request = SalaryAddRequest(
        company="Example Co", source_type="company_disclosed",
        source_name="Careers page", source_url="https://example.test/pay",
        as_of="2026-01-01", sample_size=8,
    )
    assert request.source_type == "company_disclosed"

    try:
        SalaryAddRequest(company="Example Co", source_url="javascript:alert(1)")
        assert False, "Unsafe source URLs must be rejected"
    except ValueError:
        pass

    estimate = calculate_salary_benchmark("Senior Developer", "Remote", 6)
    assert estimate["source_type"] == "modeled_estimate"
    assert estimate["is_company_reported"] is False
    assert estimate["evidence_level"] == "estimate_only"


def test_weekly_applications_count_only_confirmed_ones_from_this_week(monkeypatch):
    now = datetime.now()
    recent, old = (now - timedelta(days=2)).isoformat(), (now - timedelta(days=30)).isoformat()
    jobs = {
        "confirmed-this-week": {"status": "applied", "applied_at": recent, "first_seen": old},
        "confirmed-last-month": {"status": "applied", "applied_at": old, "first_seen": old},
        "moved-but-unconfirmed": {"status": "applied", "first_seen": old},
    }
    monkeypatch.setattr(weekly_digest, "feed_jobs", lambda: jobs)
    monkeypatch.setattr(weekly_digest, "_closing_soon_jobs", lambda: [])
    monkeypatch.setattr(weekly_digest, "calculate_funnel_metrics", lambda: {})
    monkeypatch.setattr(weekly_digest, "get_today_actions", lambda: {"counts": {}})

    assert weekly_digest.WeeklyDigestEngine().compile_digest()["metrics"]["applications_submitted"] == 1


def test_reports_escape_scraped_text_and_drop_script_links(monkeypatch, tmp_path):
    monkeypatch.setattr(report_module, "_reports_dir", lambda: tmp_path)
    hostile = {
        "title": "<script>alert(1)</script>", "company": "<img src=x onerror=alert(2)>",
        "url": "javascript:alert(3)", "match_score": 80, "status": "new",
    }

    jobs_report = report_module.html_report_generator.generate_job_search_report([hostile], {})
    pipeline_report = report_module.html_report_generator.generate_pipeline_report([{**hostile, "notes": "<b>x</b>"}])

    for report in (jobs_report, pipeline_report):
        html = Path(report["report_path"]).read_text(encoding="utf-8")
        assert "<script>alert" not in html and "<img src=x" not in html and "<b>x</b>" not in html
        assert "javascript:" not in html
        assert "&lt;script&gt;" in html


def test_feed_rows_become_report_jobs_and_unconfirmed_applications_carry_no_date():
    from backend.app.modules.scrape.job_feed import _as_seen_job

    ranked = _as_seen_job({"title": "Dev", "platform": "himalayas", "match_score": 80, "status": "Draft", "first_seen_at": "2026-10-07 00:11:20"})
    unscored = _as_seen_job({"title": "Dev", "status": None})
    moved_by_hand = _as_seen_job({"status": "Applied", "applied_at": "2026-10-06 10:00:00", "submission_confirmed": 0})
    confirmed = _as_seen_job({"status": "Applied", "applied_at": "2026-10-06 10:00:00", "submission_confirmed": 1})

    assert (ranked["status"], ranked["portal"], ranked["first_seen"]) == ("ranked", "himalayas", "2026-10-07T00:11:20")
    assert (unscored["status"], unscored["portal"]) == ("new", "unknown")
    assert (moved_by_hand["status"], moved_by_hand["applied_at"]) == ("applied", "")
    assert confirmed["applied_at"] == "2026-10-06T10:00:00"


def test_star_stubs_read_the_bullets_the_saved_profile_uses_and_claim_no_depth():
    stubs = star_framework.extract_star_candidates({
        "experience": [{"title": "Developer", "company": "Acme", "bullets": ["Built the booking flow used by two dental clinics"]}],
        "skills": ["Python"],
    })

    assert stubs[0]["what_happened"] == "Built the booking flow used by two dental clinics"
    assert not any("Deep experience" in stub["what_happened"] for stub in stubs)
