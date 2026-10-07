"""When no AI provider answers, the app must say so instead of presenting canned text as a result."""

import asyncio

import pytest

from backend.app.core import llm_client as module
from backend.app.core.llm_client import LLMUnavailable
from backend.app.modules.apply.agentic_workflow import application_pipeline
from backend.app.modules.apply.decision_maker import decision_maker_engine
from backend.app.modules.apply.form_automator import form_automator

CANNED_CLAIM = "scalable distributed systems"


@pytest.fixture
def no_provider(monkeypatch):
    monkeypatch.setattr(module.llm_client, "get_effective_provider", lambda requested=None: "none")


def test_template_reply_is_flagged(no_provider):
    result = asyncio.run(module.llm_client.generate_text("system", "user"))

    assert result["is_template_fallback"] is True


def test_cover_letter_never_uses_the_canned_letter(no_provider):
    result = asyncio.run(application_pipeline.run_pipeline_async(
        {"id": 1, "title": "Backend Developer", "company": "Acme", "description": "Python APIs"},
        {"full_name": "Ada Example", "skills": ["Python"]},
        {},
    ))

    assert CANNED_CLAIM not in result["cover_letter"]
    assert "Acme" in result["cover_letter"]
    assert module.is_template_engine(result["provider_used"])


def test_micro_portfolio_is_empty_without_a_saved_project():
    assert decision_maker_engine.synthesize_micro_portfolio("Backend Developer", "Acme", []) == ""


@pytest.mark.parametrize("question", [
    "Will you now or in the future require visa sponsorship?",
    "How many years of experience do you have with Python?",
    "What is your GitHub profile?",
])
def test_form_answers_are_not_guessed_when_the_profile_does_not_say(question):
    result = form_automator.answer_question(question, {"skills": ["python"]})

    assert result["status"] == "REQUIRES_HUMAN_INPUT"


def test_form_answers_come_from_the_profile_when_it_has_them():
    years = form_automator.answer_question("Years of experience?", {"years_of_experience": 6})
    github = form_automator.answer_question("GitHub profile?", {"github_url": "https://github.com/ada"})

    assert (years["answer"], years["status"]) == ("6 years", "AUTO_FILLED")
    assert (github["answer"], github["status"]) == ("https://github.com/ada", "AUTO_FILLED")


def test_linkedin_message_states_only_saved_facts():
    bare = decision_maker_engine.draft_three_sentence_outreach("Acme", "Backend Developer", {})
    full = decision_maker_engine.draft_three_sentence_outreach(
        "Acme", "Backend Developer", {"skills": ["Python", "SQL", "Go"]}, {"title": "Billing API", "metrics": "40% faster invoices"},
    )
    no_result = decision_maker_engine.draft_three_sentence_outreach("Acme", "Dev", {"skills": ["Python"]}, {"title": "Billing API"})

    for text in (bare, full, no_result):
        assert not any(claim in text for claim in ("distributed systems", "strong background", "reliable architectures", "performance gains", "following"))
    assert "Python and SQL" in full and "Billing API (40% faster invoices)" in full and "Go" not in full
    assert no_result.count("(") == 0


def test_offline_cover_letter_template_makes_no_generic_claims(no_provider):
    letter = asyncio.run(application_pipeline.run_pipeline_async(
        {"id": 1, "title": "Backend Developer", "company": "Acme", "description": "Python APIs"},
        {"full_name": "Ada Example", "skills": ["Python", "FastAPI"]},
        {},
    ))["cover_letter"]

    assert "Python" in letter and "Ada Example" in letter
    assert not any(claim in letter for claim in ("worked extensively", "hands-on experience", "dependable systems", "caught my attention"))
