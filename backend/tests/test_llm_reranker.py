"""AI review of top-ranked jobs: validated, cached per profile version, and never fatal to ranking."""

import asyncio
import json
import sqlite3

import pytest

from backend.app.modules.rank import llm_reranker as rr


class _Shared:
    """One in-memory database handed out repeatedly; close() is a no-op so it survives."""

    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return self._connection.cursor()

    def commit(self):
        self._connection.commit()

    def close(self):
        pass


@pytest.fixture
def jobs_db(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("""CREATE TABLE scraped_jobs (id TEXT, title TEXT, company TEXT, location TEXT, remote_type TEXT,
        description TEXT, match_score REAL, match_tier TEXT, match_status TEXT, red_flags TEXT, ai_review_json TEXT DEFAULT '',
        status TEXT, stale_at TEXT)""")
    connection.executemany(
        "INSERT INTO scraped_jobs(id, title, company, location, remote_type, description, match_score, red_flags, status, stale_at) VALUES (?, ?, 'Acme', 'Remote', 'Remote', 'desc', ?, ?, ?, ?)",
        [
            ("senior", "Senior Staff Engineer", 80, "[]", "Draft", None),
            ("junior", "Junior Developer", 60, "[]", None, None),
            ("flagged", "Developer (on-site)", 55, '["Konum uyuşmuyor"]', "Draft", None),
            ("applied", "Already Applied", 99, "[]", "Applied", None),
            ("stale", "Old Listing", 99, "[]", "Draft", "2026-01-01"),
        ],
    )
    monkeypatch.setattr(rr, "get_db_connection", lambda: _Shared(connection))
    monkeypatch.setattr(rr, "ensure_profile_version", lambda profile: profile.get("_version", 1))
    monkeypatch.setattr(rr.llm_client, "get_effective_provider", lambda *args: "anthropic")
    return connection


def _model(monkeypatch, replies, provider="Anthropic (claude-sonnet-5-5)"):
    prompts = []

    async def generate_text(system_prompt, user_prompt, **kwargs):
        prompts.append(user_prompt)
        title = next(key for key in replies if f"Title: {key}\n" in user_prompt)
        reply = replies[title]
        if isinstance(reply, Exception):
            raise reply
        return {"text": reply if isinstance(reply, str) else json.dumps(reply), "provider_used": provider}

    monkeypatch.setattr(rr.llm_client, "generate_text", generate_text)
    return prompts


def _row(connection, job_id):
    row = dict(connection.execute("SELECT * FROM scraped_jobs WHERE id = ?", (job_id,)).fetchone())
    row["ai_review"] = json.loads(row["ai_review_json"] or "null")
    return row


PROFILE = {"target_role": "Junior Developer", "skills": ["Python"], "years_of_experience": 0, "raw_cv_text": "Student."}


def test_ai_scores_replace_rule_scores_only_for_fresh_unapplied_jobs(jobs_db, monkeypatch):
    prompts = _model(monkeypatch, {
        "Senior Staff Engineer": {"score": 22, "verdict": "Kıdem çok yüksek.", "strengths": ["Python"], "gaps": ["8+ yıl deneyim"]},
        "Junior Developer": "```json\n{\"score\": 88, \"verdict\": \"Güçlü uyum.\", \"strengths\": [], \"gaps\": []}\n```",
        "Developer (on-site)": {"score": 90, "verdict": "Uygun ama konum sorunlu.", "strengths": [], "gaps": []},
    })

    summary = asyncio.run(rr.review_top_jobs(PROFILE))

    assert summary == {"status": "success", "reviewed": 3, "reused": 0, "failed": 0}
    assert len(prompts) == 3 and all("Student." in prompt for prompt in prompts)
    senior, junior, flagged = _row(jobs_db, "senior"), _row(jobs_db, "junior"), _row(jobs_db, "flagged")
    assert (senior["match_score"], senior["match_tier"], senior["match_status"]) == (22, "Low", "Fail")
    assert (junior["match_score"], junior["match_tier"]) == (88, "High")
    assert senior["ai_review"]["rule_score"] == 80 and senior["ai_review"]["gaps"] == ["8+ yıl deneyim"]
    # A red flag still keeps a high AI score out of the High tier.
    assert (flagged["match_score"], flagged["match_tier"]) == (90, "Medium")
    assert _row(jobs_db, "applied")["match_score"] == 99 and _row(jobs_db, "stale")["ai_review"] is None


def test_reviews_are_reused_until_the_profile_changes(jobs_db, monkeypatch):
    replies = {title: {"score": 70, "verdict": "ok"} for title in ("Senior Staff Engineer", "Junior Developer", "Developer (on-site)")}
    prompts = _model(monkeypatch, replies)
    asyncio.run(rr.review_top_jobs(PROFILE))
    jobs_db.execute("UPDATE scraped_jobs SET match_score = 10")  # what the next rule pass does

    again = asyncio.run(rr.review_top_jobs(PROFILE))
    assert again == {"status": "success", "reviewed": 0, "reused": 3, "failed": 0}
    assert len(prompts) == 3 and _row(jobs_db, "junior")["match_score"] == 70

    changed = asyncio.run(rr.review_top_jobs({**PROFILE, "_version": 2}))
    assert changed["reviewed"] == 3 and len(prompts) == 6


def test_unusable_or_failed_reviews_leave_the_rule_score(jobs_db, monkeypatch):
    _model(monkeypatch, {
        "Senior Staff Engineer": "I cannot judge this.",
        "Junior Developer": {"score": 250, "verdict": "out of range"},
        "Developer (on-site)": RuntimeError("network down"),
    })
    summary = asyncio.run(rr.review_top_jobs(PROFILE))
    assert summary == {"status": "failed", "reviewed": 0, "reused": 0, "failed": 3}
    assert _row(jobs_db, "senior")["match_score"] == 80 and _row(jobs_db, "senior")["ai_review"] is None


def test_template_fallback_text_is_never_treated_as_a_judgement(jobs_db, monkeypatch):
    replies = {title: {"score": 95, "verdict": "x"} for title in ("Senior Staff Engineer", "Junior Developer", "Developer (on-site)")}
    _model(monkeypatch, replies, provider="Fallback Engine (API Error)")
    assert asyncio.run(rr.review_top_jobs(PROFILE))["reviewed"] == 0
    assert _row(jobs_db, "junior")["match_score"] == 60


def test_without_an_ai_provider_the_review_is_skipped(jobs_db, monkeypatch):
    monkeypatch.setattr(rr.llm_client, "get_effective_provider", lambda *args: "local_fallback")
    assert asyncio.run(rr.review_top_jobs(PROFILE))["status"] == "skipped"


@pytest.mark.parametrize("raw", [{}, {"score": "high"}, {"score": -1}, {"verdict": "no score"}, None])
def test_invalid_model_output_is_rejected(raw):
    assert rr.parse_review(raw) is None


def test_valid_model_output_is_trimmed():
    review = rr.parse_review({"score": "81.26", "verdict": " İyi ", "strengths": ["a", "b", "c", "d"], "gaps": "none"})
    assert review == {"score": 81.3, "verdict": "İyi", "strengths": ["a", "b", "c"], "gaps": []}
