"""When no AI provider answers, the app must say so instead of presenting canned text as a result."""

import asyncio

import pytest

from backend.app.core import llm_client as module
from backend.app.core.llm_client import LLMUnavailable
from backend.app.modules.apply.agentic_workflow import application_pipeline
from backend.app.modules.apply.cold_outreach import cold_outreach_engine
from backend.app.modules.apply.decision_maker import decision_maker_engine
from backend.app.modules.apply.form_automator import form_automator
from backend.app.modules.interview.offer_negotiator import offer_negotiator_engine
from backend.app.modules.setup.career_discovery import career_discovery_engine
from backend.app.modules.setup.profile_optimizer import profile_optimizer_agent

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


def test_career_roadmap_fails_instead_of_returning_a_cover_letter(no_provider):
    with pytest.raises(LLMUnavailable):
        asyncio.run(career_discovery_engine.generate_ai_career_roadmaps({"target_role": "Backend"}, "Data Engineer"))


def test_outreach_fails_instead_of_inventing_an_achievement(no_provider):
    with pytest.raises(LLMUnavailable):
        asyncio.run(cold_outreach_engine.generate_executive_outreach(
            "Sam", "Engineering Manager", "Acme", "Backend Developer", {"skills": ["Python"]},
        ))


def test_outreach_survives_a_model_that_returns_no_subject_lines(monkeypatch):
    async def reply(**kwargs):
        return {"subject_lines": "not a list", "email_body": "Hello Sam."}

    monkeypatch.setattr(module.llm_client, "generate_json", reply)

    result = asyncio.run(cold_outreach_engine.generate_executive_outreach(
        "Sam", "Engineering Manager", "Acme", "Backend Developer", {"skills": ["Python"]},
    ))

    assert "Acme" in result["subject"]
    assert result["body"] == "Hello Sam."


def test_offer_letter_and_linkedin_profile_fail_without_a_provider(no_provider):
    with pytest.raises(LLMUnavailable):
        asyncio.run(offer_negotiator_engine.generate_counter_offer_letter(
            company="Acme", title="Backend Developer", offered_base=50000, target_base=60000,
        ))
    with pytest.raises(LLMUnavailable):
        asyncio.run(profile_optimizer_agent.optimize_linkedin_profile({"target_role": "Backend", "skills": ["Python"]}))


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


def test_profile_prompts_assume_no_experience_or_repositories(monkeypatch):
    prompts = []

    async def capture(**kwargs):
        prompts.append(kwargs["user_prompt"])
        return {"ok": True}

    monkeypatch.setattr(module.llm_client, "generate_json", capture)

    asyncio.run(profile_optimizer_agent.optimize_linkedin_profile({"target_role": "Backend", "skills": ["Python"]}))
    asyncio.run(profile_optimizer_agent.audit_github_profile("ada"))
    asyncio.run(profile_optimizer_agent.audit_github_profile("ada", [{"name": "billing-api"}]))

    assert "Years of Experience: not specified" in prompts[0]
    assert "Autonomous-Career-Agent" not in prompts[1] and "do not assume any repository" in prompts[1]
    assert "billing-api" in prompts[2]
