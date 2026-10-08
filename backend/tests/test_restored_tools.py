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
    complete = star_framework.score_star_answer({
        "situation": "During a production release, our booking team faced a concurrency problem that caused duplicate appointments.",
        "task": "My goal was to stop the duplicate bookings without taking the service offline.",
        "action": "I designed a Python lock, added a retry path, and wrote tests because the losing request needed a safe recovery.",
        "result": "As a result, duplicate bookings fell from 12 per week to zero and support tickets dropped by 30%.",
    })
    partial = star_framework.score_star_answer({"situation": "A project had a problem", "task": "My task was to help", "result": "It went well"})

    assert (complete["overall_score"], complete["is_complete"], complete["has_metrics"]) == (90.0, True, True)
    padded_complete = {
        key: value + " additional wording" * 80 for key, value in {
            "situation": "During a production release, our booking team faced a concurrency problem that caused duplicate appointments.",
            "task": "My goal was to stop the duplicate bookings without taking the service offline.",
            "action": "I designed a Python lock, added a retry path, and wrote tests because the losing request needed a safe recovery.",
            "result": "As a result, duplicate bookings fell from 12 per week to zero and support tickets dropped by 30%.",
        }.items()
    }
    assert star_framework.score_star_answer(padded_complete)["component_scores"] == complete["component_scores"]
    assert partial["component_scores"] == {"situation": 90, "task": 60, "action": 0, "result": 30}
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


def test_interview_questions_follow_the_posting_and_the_cv():
    from backend.app.modules.interview.interview_simulator import interview_simulator

    def session(have, missing, description):
        return interview_simulator.generate_interview_session(
            "Backend Developer", "Acme", description, {"keywords_you_have": have, "keywords_missing": missing},
        )

    backend = session(["Python", "PostgreSQL"], ["Kubernetes"], "You will lead a team and design systems.")
    frontend = session(["React"], [], "Build interfaces.")
    text = lambda questions: " ".join(q["question"] for q in questions)

    assert "Python" in text(backend) and "PostgreSQL" in text(backend) and "Kubernetes" in text(backend)
    assert "React" in text(frontend) and "Python" not in text(frontend)
    assert "Acme" in backend[0]["question"]
    assert [q["id"] for q in backend] == [f"q{n}" for n in range(1, len(backend) + 1)]
    assert all(q["type"] and q["key_points"] for q in backend + frontend)
    # A leadership posting gets a leadership question; the plain one does not.
    assert any(q["type"] == "Liderlik & İnisiyatif" for q in backend)
    assert not any(q["type"] == "Liderlik & İnisiyatif" for q in frontend)
    assert "scraping" not in text(backend).lower() and "bypass" not in text(backend).lower()
    # With nothing to go on it still asks about the role itself, never a canned stack.
    assert "Backend Developer" in text(session([], [], ""))


TECH_QUESTION = "This role asks for Python. Walk me through a piece of work where you used Python: the problem, what you did, and how it turned out."
STRONG_ANSWER = (
    "When I worked as a freelance engineer, a client's booking system was double-booking appointments during busy hours. "
    "My task was to stop the collisions without taking the system offline. I wrote a Python service that takes a row lock "
    "before confirming a slot, added a retry for the losing request, and covered both paths with tests. "
    "As a result double bookings dropped from about 12 a week to 0, and support tickets about scheduling fell by 80%."
)


def _evaluate(question, answer):
    from backend.app.modules.interview.interview_simulator import interview_simulator
    return interview_simulator.evaluate_candidate_answer(question, answer)


def test_a_complete_answer_scores_high_and_every_check_is_explained():
    result = _evaluate(TECH_QUESTION, STRONG_ANSWER)

    assert result["score"] >= 85 and result["grade"] == "EXCELLENT"
    assert len(result["feedback"]) == len(result["checks"]) == 6
    assert all(check["passed"] for check in result["checks"])


def test_long_text_without_substance_no_longer_scores_well():
    padding = "I think this is a very interesting question and there are many things to consider about it in general. " * 4

    result = _evaluate(TECH_QUESTION, padding)

    assert result["score"] <= 30 and result["grade"] == "NEEDS_IMPROVEMENT"
    missed = {check["id"] for check in result["checks"] if not check["passed"]}
    assert {"on_topic", "own_action", "result", "evidence"} <= missed


def test_each_missing_part_costs_points_and_the_tip_names_the_biggest_gap():
    without_evidence = (
        STRONG_ANSWER
        .replace("covered both paths with tests", "worked on both paths")
        .replace("support tickets", "the team")
        .replace("about 12 a week to 0", "sharply")
        .replace("by 80%", "a lot")
    )
    off_topic = STRONG_ANSWER.replace("Python", "Ruby")

    assert _evaluate(TECH_QUESTION, without_evidence)["score"] < _evaluate(TECH_QUESTION, STRONG_ANSWER)["score"]
    off = _evaluate(TECH_QUESTION, off_topic)
    assert not next(check for check in off["checks"] if check["id"] == "on_topic")["passed"]
    assert "Python" in off["coaching_tip"]


def test_behavioural_questions_are_not_marked_down_for_naming_no_technology_and_empty_answers_score_zero():
    behavioural = _evaluate("Describe a time you had to work with a difficult team member.", STRONG_ANSWER)

    assert [check["id"] for check in behavioural["checks"]].count("on_topic") == 0
    assert behavioural["score"] >= 85
    assert _evaluate(TECH_QUESTION, "   ")["score"] == 0


def test_answer_score_does_not_change_when_only_length_changes():
    concise = "I built a Python API for a client project. As a result tests passed and users could book reliably."
    padded = concise + " " + "extra context " * 80

    assert _evaluate(TECH_QUESTION, concise)["score"] == _evaluate(TECH_QUESTION, padded)["score"]
    assert {check["id"] for check in _evaluate(TECH_QUESTION, concise)["checks"]} == {
        "on_topic", "own_action", "context", "result", "evidence", "reasoning",
    }


@pytest.mark.parametrize("technology", ["Next.js", ".NET", "C++"])
def test_technology_names_with_punctuation_are_not_truncated(technology):
    from backend.app.modules.interview.interview_simulator import interview_simulator

    questions = interview_simulator.generate_interview_session(
        "Developer", "Acme", "", {"keywords_you_have": [technology]},
    )
    question = next(q["question"] for q in questions if q["type"] == "Technical")
    result = _evaluate(question, f"i built a {technology} service for a client project.")
    assert next(c for c in result["checks"] if c["id"] == "on_topic")["passed"]
    assert next(c for c in result["checks"] if c["id"] == "own_action")["passed"]


def test_year_and_substrings_do_not_count_as_result_evidence():
    result = _evaluate(TECH_QUESTION, "In 2024 I built a Python catalog for a contest.")
    assert not next(c for c in result["checks"] if c["id"] == "evidence")["passed"]
    assert result["technical_correctness_verified"] is False


def test_turkish_action_and_measurement_are_recognized():
    result = _evaluate(TECH_QUESTION, "Müşteri için Python API geliştirdim. Sonuç olarak hatalar %30 azaldı.")
    checks = {c["id"]: c["passed"] for c in result["checks"]}
    assert checks["own_action"] and checks["evidence"] and checks["result"]


def test_voice_content_score_matches_written_and_is_independent_of_pace_and_padding():
    from backend.app.modules.interview.voice_coach import voice_coach

    base = voice_coach.evaluate_vocal_performance(TECH_QUESTION, STRONG_ANSWER, 30)
    slower = voice_coach.evaluate_vocal_performance(TECH_QUESTION, STRONG_ANSWER, 120)
    padded = voice_coach.evaluate_vocal_performance(TECH_QUESTION, STRONG_ANSWER + " um extra wording" * 80, 30)
    assert base["overall_score"] == slower["overall_score"] == padded["overall_score"] == _evaluate(TECH_QUESTION, STRONG_ANSWER)["score"]
    assert base["wpm"] != slower["wpm"]
    assert base["fluency_score"] != padded["fluency_score"]
    assert base["content_evaluation"]["checks"] == slower["content_evaluation"]["checks"]


@pytest.mark.parametrize("answer", ["", "   ", "latency database api cache async docker pipeline microservice testing scale throughput memory redis fastapi " * 30])
def test_empty_voice_or_jargon_alone_cannot_earn_points(answer):
    from backend.app.modules.interview.voice_coach import voice_coach

    result = voice_coach.evaluate_vocal_performance(TECH_QUESTION, answer, 30)
    assert result["overall_score"] == 0


def test_interview_scoring_endpoints_share_the_content_rubric():
    written = client.post("/api/interview/evaluate", json={"question": TECH_QUESTION, "answer": STRONG_ANSWER})
    spoken = client.post("/api/interview/voice_evaluate", json={"question": TECH_QUESTION, "transcript": STRONG_ANSWER, "duration_seconds": 20})
    assert written.status_code == spoken.status_code == 200
    assert written.json() == spoken.json()["content_evaluation"]
    assert spoken.json()["overall_score"] == written.json()["score"]
