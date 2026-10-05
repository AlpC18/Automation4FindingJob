"""Regressions found by the first real end-to-end run: ranking, draft provenance, deadlines, weekly counts."""

import sqlite3
from datetime import date, datetime, timedelta

from backend.app.core.llm_client import is_template_engine, llm_client
from backend.app.modules.outcome import today as today_module
from backend.app.modules.outcome import weekly_digest
from backend.app.modules.rank import scoring_engine
from backend.app.modules.scrape.live_sources import normalize_job

BACKEND_DEV = {
    "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"], "years_of_experience": 4,
    "target_role": "Python Backend Developer", "target_roles": ["Python Backend Developer"],
}


def _score(title, description, profile=BACKEND_DEV, monkeypatch=None):
    return scoring_engine.score_job_against_profile({"id": "j", "title": title, "description": description, "location": "Remote"}, profile)


def test_one_shared_keyword_in_an_unrelated_role_is_not_a_high_match(monkeypatch):
    monkeypatch.setattr(scoring_engine, "calculate_salary_benchmark", lambda *args: {})
    unrelated = _score("Business Intelligence Analyst", "Dashboards in Power BI; some Python scripting.")
    related = _score("Senior Backend Engineer (Python)", "Python, FastAPI, PostgreSQL and Docker in production.")

    assert unrelated["match_tier"] != "High" and unrelated["match_score"] < 70
    assert related["match_tier"] == "High" and related["match_score"] >= 90
    explanation = unrelated["skill_gaps"]["score_explanation"]
    assert explanation["role_points"] == 0 and explanation["role_points_max"] == 30


def test_role_relevance_handles_synonyms_seniority_and_missing_target_role():
    assert scoring_engine.role_relevance("Senior Back-End Engineer", ["Backend Developer"]) == 1.0
    assert scoring_engine.role_relevance("Data Analyst", ["Python Backend Developer"]) == 0
    assert scoring_engine.role_relevance("Python Developer", ["Data Analyst", "Python Backend Developer"]) == 2 / 3
    assert scoring_engine.role_relevance("Anything", []) is None


def test_auto_provider_means_the_configured_default(monkeypatch):
    monkeypatch.setattr(llm_client, "provider", "anthropic")
    assert llm_client.get_effective_provider("auto") == "anthropic"
    assert llm_client.get_effective_provider(None) == "anthropic"
    assert llm_client.get_effective_provider("gemini") == "gemini"


def test_template_engine_output_is_recognised():
    assert is_template_engine("Fallback Engine (API Error)")
    assert is_template_engine("Fallback (Empty output rescued)")
    assert is_template_engine("Deterministic Hybrid Engine")
    assert not is_template_engine("Anthropic (claude-sonnet-5-5)")
    assert not is_template_engine("")


def test_sources_deadline_is_kept_as_an_iso_date():
    job = normalize_job({"title": "Dev", "url": "https://x.test/1", "deadline": "2026-11-02 23:50:00"}, "kosovajob")
    assert job["deadline"] == "2026-11-02"
    assert normalize_job({"title": "Dev", "url": "https://x.test/2", "deadline": "soon"}, "x")["deadline"] == ""


def test_closing_soon_lists_only_fresh_high_matches_inside_the_window(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE scraped_jobs (id TEXT, title TEXT, company TEXT, deadline TEXT, status TEXT, stale_at TEXT, match_score REAL)")
    connection.executemany("INSERT INTO scraped_jobs VALUES (?, 'T', 'C', ?, ?, ?, ?)", [
        ("due-tomorrow", "2026-10-06", "Draft", None, 85),
        ("due-in-3", "2026-10-08", None, None, 71),
        ("too-far", "2026-10-20", "Draft", None, 90),
        ("already-closed", "2026-10-01", "Draft", None, 90),
        ("low-match", "2026-10-06", "Draft", None, 40),
        ("already-applied", "2026-10-06", "Applied", None, 90),
        ("stale", "2026-10-06", "Draft", "2026-10-01", 90),
        ("no-deadline", "", "Draft", None, 90),
    ])
    monkeypatch.setattr(today_module, "get_db_connection", lambda: _Unclosable(connection))

    jobs = today_module._closing_soon_jobs(today=date(2026, 10, 5))
    assert [(job["id"], job["days_left"]) for job in jobs] == [("due-tomorrow", 1), ("due-in-3", 3)]


class _Unclosable:
    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return self._connection.cursor()

    def close(self):
        pass


def test_weekly_applications_count_only_confirmed_ones_from_this_week(monkeypatch):
    now = datetime.now()
    recent, old = (now - timedelta(days=2)).isoformat(), (now - timedelta(days=30)).isoformat()
    jobs = {
        "confirmed-this-week": {"status": "applied", "applied_at": recent, "first_seen": old},
        "confirmed-last-month": {"status": "applied", "applied_at": old, "first_seen": old},
        "moved-but-unconfirmed": {"status": "applied", "first_seen": old},
    }
    monkeypatch.setattr(weekly_digest.seen_jobs_tracker, "get_all", lambda: jobs)
    monkeypatch.setattr(weekly_digest.seen_jobs_tracker, "get_closing_soon", lambda days=5: [])
    monkeypatch.setattr(weekly_digest, "calculate_funnel_metrics", lambda: {})
    monkeypatch.setattr(weekly_digest, "get_today_actions", lambda: {"counts": {}})

    assert weekly_digest.WeeklyDigestEngine().compile_digest()["metrics"]["applications_submitted"] == 1


def test_cover_letter_prompt_is_grounded_in_the_cv_and_never_invents_a_background():
    from backend.app.modules.apply.agentic_workflow import build_cover_letter_prompt

    job = {"title": "Junior Backend Developer", "company": "Acme", "location": "Prishtina", "description": "Node.js ve PostgreSQL. " + "x" * 5000}
    profile = {
        "full_name": "Test Aday", "target_role": "Junior Developer", "years_of_experience": 0, "languages": ["Turkish", "English"],
        "skills": ["Node.js", "PostgreSQL"], "raw_cv_text": "Student at UBT. Built Dentify with PostgreSQL GiST exclusion constraints.",
    }
    prompt = build_cover_letter_prompt(job, profile, [])

    assert "Built Dentify with PostgreSQL GiST exclusion constraints." in prompt
    assert "Years of professional experience: 0" in prompt
    assert "(none saved; rely on the CV text)" in prompt
    assert "General software engineering background" not in prompt and "scalable systems" not in prompt
    assert "Do not invent" in prompt and "student" in prompt.lower()
    assert len(prompt) < 9000  # the long description is truncated

    with_project = build_cover_letter_prompt(job, profile, [{"title": "LeadScout", "content": "Lead agent", "tech_stack": ["Python"], "metrics": ""}])
    assert "- LeadScout: Lead agent (stack: Python; result: not recorded)" in with_project


def test_senior_titles_are_pushed_down_for_candidates_with_little_experience(monkeypatch):
    monkeypatch.setattr(scoring_engine, "calculate_salary_benchmark", lambda *args: {})
    description = "Python, FastAPI, PostgreSQL and Docker in production."
    junior_profile = {**BACKEND_DEV, "years_of_experience": 1}

    senior_job = _score("Senior Backend Developer (Python)", description, junior_profile)
    plain_job = _score("Backend Developer (Python)", description, junior_profile)
    assert plain_job["match_score"] - senior_job["match_score"] == 25
    assert senior_job["skill_gaps"]["score_explanation"]["seniority_deduction"] == 25
    assert senior_job["match_tier"] != "High"

    experienced = _score("Senior Backend Developer (Python)", description, {**BACKEND_DEV, "years_of_experience": 6})
    assert experienced["skill_gaps"]["score_explanation"]["seniority_deduction"] == 0
    unknown = _score("Lead Engineer", description, {"skills": ["Python"]})
    assert unknown["skill_gaps"]["score_explanation"]["seniority_deduction"] == 0
