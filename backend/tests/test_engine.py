"""
Comprehensive Test Suite for Autonomous Career Agent Engine
Covers:
1. Anti-AI Humanizer Engine & Forbidden Lexicon
2. RAG Context Memory Storage & Retrieval
3. Ghost Job Scoring & Stagnancy Checks
4. Red Flag & Seniority Mismatch Detectors
5. Decision Maker Google X-Ray Dork Construction
6. Dynamic Form Answer Memory
7. Account Safety Quota Limiter
8. TestSprite Autonomous QA Runner
"""

import pytest
from backend.app.modules.scrape.seen_jobs_tracker import SeenJobsTracker
from backend.app.modules.apply.humanizer_engine import humanizer_engine
from backend.app.modules.setup.rag_engine import RAGVectorMemory
from backend.app.modules.scrape.ghost_job_detector import evaluate_ghost_job
from backend.app.modules.rank.red_flag_detector import detect_red_flags
from backend.app.modules.apply.decision_maker import decision_maker_engine
from backend.app.modules.apply.form_automator import form_automator
from backend.app.modules.scrape.rate_limiter import account_health
from backend.app.modules.testsprite.test_runner import testsprite_runner
from backend.app.modules.rank import scoring_engine

def test_anti_ai_humanizer_detects_forbidden_words():
    sample = "I am delighted to apply. I spearheaded the project to create a seamless integration in this dynamic ecosystem."
    found = humanizer_engine.scan_forbidden_words(sample)
    assert "delighted to apply" in found
    assert "spearheaded" in found
    assert "seamless integration" in found
    assert "dynamic ecosystem" in found

def test_anti_ai_humanizer_sanitizes_text():
    sample = "I am delighted to apply and spearheaded the seamless integration."
    cleaned = humanizer_engine.replace_forbidden_buzzwords(sample)
    leftover = humanizer_engine.scan_forbidden_words(cleaned)
    assert len(leftover) == 0
    assert "writing to apply" in cleaned
    assert "led" in cleaned

def test_rag_memory_semantic_search(tmp_path):
    memory = RAGVectorMemory(tmp_path / "rag.json")
    memory.add_project(
        "Candidate scraping project",
        "Built a Python scraping pipeline with proxy rotation.",
        ["Python", "Playwright"],
        "",
    )
    results = memory.search_relevant_context("Looking for a Python scraping and proxy expert", top_k=1)
    assert len(results) > 0
    assert any("python" in t.lower() or "scraping" in t.lower() for t in results[0]["tags"])


def test_seen_jobs_applied_stage_keeps_submission_unconfirmed(tmp_path):
    tracker = SeenJobsTracker(tmp_path / "seen_jobs.json")
    key, is_new = tracker.add("Example Co", "Platform Engineer", "https://example.test/job")
    assert is_new is True

    assert tracker.mark_applied(key, "Kanban move", confirmed=False) is True
    pending = tracker.get_all()[key]
    assert pending["status"] == "applied"
    assert pending["submission_confirmed"] is False
    assert pending["application_execution_mode"] == "simulation"
    assert "applied_at" not in pending

    assert tracker.mark_applied(key, "Portal receipt", confirmed=True) is True
    confirmed = tracker.get_all()[key]
    assert confirmed["submission_confirmed"] is True
    assert confirmed["application_execution_mode"] == "live"
    assert confirmed["applied_at"]

def test_ghost_job_scoring_high_risk():
    stagnant_job = {
        "title": "Developer",
        "posted_date": "50 days ago",
        "description": "Reposted: rockstar in fast-paced environment to wear many hats.",
        "salary_range": "Not disclosed",
        "applicants_count": 300
    }
    score, reasons, rec = evaluate_ghost_job(stagnant_job)
    assert score >= 50.0
    assert len(reasons) >= 3

def test_red_flag_detection():
    job = {
        "title": "Remote Senior Backend Engineer",
        "remote_type": "Remote",
        "description": "Position is full-time. In-office 4 days every week. Must have active security clearance.",
        "location": "Washington, DC"
    }
    cand_profile = {"work_preference": "remote", "years_of_experience": 2}
    flags = detect_red_flags(job, cand_profile)
    assert len(flags) >= 2
    assert any("Çelişkili Çalışma Modeli" in f for f in flags)
    assert any("Güvenlik Soruşturması" in f for f in flags)

def test_match_explanation_uses_profile_evidence_and_does_not_invent_experience(monkeypatch):
    monkeypatch.setattr(scoring_engine, "calculate_salary_benchmark", lambda title, location, years: {"years_used": years})
    result = scoring_engine.score_job_against_profile(
        {"id": "job-1", "title": "Python Backend Engineer", "description": "Python and FastAPI experience required", "location": "Remote"},
        {"skills": ["Python"]},
    )

    explanation = result["skill_gaps"]["score_explanation"]
    assert explanation["experience_missing"] is True
    assert explanation["experience_years_used"] is None
    assert result["salary_benchmark"]["years_used"] is None
    assert result["skill_gaps"]["matched_evidence"] == [{"required_skill": "python", "profile_evidence": "Python", "evidence_source": "profile_skill"}]
    assert "not an employer ATS score" in explanation["caveat"]

def test_match_explanation_can_cite_explicit_skill_from_saved_cv(monkeypatch):
    monkeypatch.setattr(scoring_engine, "calculate_salary_benchmark", lambda title, location, years: {})
    result = scoring_engine.score_job_against_profile(
        {"id": "job-2", "title": "Python Engineer", "description": "Python and FastAPI required", "location": "Remote"},
        {"skills": [], "raw_cv_text": "Built backend services using Python and FastAPI."},
    )
    assert {item["required_skill"] for item in result["skill_gaps"]["matched_evidence"]} == {"python", "fastapi"}
    assert all(item["evidence_source"] == "saved_cv_text" for item in result["skill_gaps"]["matched_evidence"])

def test_decision_maker_xray_dork():
    dork = decision_maker_engine.generate_xray_dork("Cognitive Scale AI", "Istanbul")
    assert 'site:linkedin.com/in/' in dork
    assert '"Cognitive Scale AI"' in dork
    assert '"Istanbul"' in dork
    assert '("Manager" OR "Director" OR "Lead"' in dork

def test_form_memory_retrieval():
    res = form_automator.answer_question(
        "Will you now or in the future require visa sponsorship?",
        {"skills": ["python"]}
    )
    assert res["answer"] == "No"
    assert res["source"] == "FORM_MEMORY"

def test_account_health_quota():
    allowed, msg, metrics = account_health.can_perform_action("linkedin", "apply")
    assert allowed is True
    assert metrics["limit"] > 0

def test_testsprite_autonomous_suite():
    suite_res = testsprite_runner.run_all_e2e_tests()
    assert suite_res["suite_status"] == "PASSED"
    assert suite_res["failed_tests"] == 0
