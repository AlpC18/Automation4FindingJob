"""A drafted letter is checked against the CV and saved projects; what they do not back up is flagged."""

from backend.app.modules.apply.claim_check import find_unsupported_claims
import pytest
from datetime import date

PROFILE = {
    "skills": ["Python", "FastAPI", "Java", "MySQL", "MongoDB", "PostgreSQL", "Node.js", "TypeScript"],
    "raw_cv_text": "Ada Example. Freelance software engineer 2025 – Present. UBT Prishtina. GDPR compliant workflows.",
}
PROJECTS = [
    {"title": "ClearMark / AI Watermark Removal Engine", "tech_stack": ["Python", "FastAPI", "PyTorch", "Celery", "Redis", "Docker"],
     "content": "Full-stack image inpainting web application with an asynchronous Celery + Redis GPU task queue."},
    {"title": "OutreachPulse", "tech_stack": ["Node.js", "TypeScript", "Fastify 5", "PostgreSQL", "Prisma 6", "BullMQ", "Redis"],
     "content": "Self-hosted B2B outreach engine with AES-256-GCM credential encryption at rest and GDPR compliant workflows."},
]
JOB = {"title": "Back-end Developer intern - Python", "company": "Workforce Development Solutions", "description": "Python, REST APIs, Kubernetes"}


@pytest.fixture
def student_profile():
    return {"raw_cv_text": "Currently a Computer Science student at university in Kosovo.", "education": [
        {"degree": "Bachelor of Computer Science", "year": f"{date.today().year - 2} – {date.today().year + 1}"},
        {"degree": "High School Diploma", "year": "2020 – 2023"},
    ]}


@pytest.mark.parametrize("letter", [
    "As a recent Computer Science graduate, I would like to apply.",
    "I am a Computer Science graduate.",
    "With a Bachelor’s degree in Computer Science, I build software.",
    "I hold a bachelor's degree in Computer Science.",
    "Bilgisayar mühendisliği lisans mezunuyum.",
])
def test_ongoing_studies_cannot_be_presented_as_graduation(student_profile, letter):
    assert any("ongoing studies" in c["reason"] for c in find_unsupported_claims(letter, student_profile, [], {}))


@pytest.mark.parametrize("letter", [
    "I am currently pursuing a bachelor's degree in Computer Science.",
    "I am not a university graduate yet.",
    "I expect to graduate next year.",
    "I will graduate next year.",
    "I am a high school graduate and a current university student.",
    "The position requires a bachelor's degree.",
    "Henüz lisans mezunu değilim.",
])
def test_student_wording_and_completed_school_are_not_flagged(student_profile, letter):
    assert find_unsupported_claims(letter, student_profile, [], {}) == []


def test_completed_bachelor_is_valid_while_studying_for_master(student_profile):
    student_profile["education"][0]["status"] = "completed"
    student_profile["education"].append({"degree": "Master of Computer Science", "status": "in progress"})
    assert find_unsupported_claims("I hold a bachelor's degree in Computer Science.", student_profile, [], {}) == []
    assert find_unsupported_claims("I hold a master's degree in Computer Science.", student_profile, [], {})


def test_student_status_in_cv_and_prompt_is_preserved(student_profile):
    from backend.app.modules.apply.agentic_workflow import build_cover_letter_prompt
    prompt = build_cover_letter_prompt({}, student_profile, [])
    assert "Ongoing studies (not completed degrees)" in prompt
    assert student_profile["education"][0]["year"] in prompt
    assert "never say" in prompt
    assert find_unsupported_claims("I am a recent Computer Science graduate.", {"raw_cv_text": student_profile["raw_cv_text"]}, [], {})


def _reasons(letter):
    return [claim["reason"] for claim in find_unsupported_claims(letter, PROFILE, PROJECTS, JOB)]


def test_a_letter_built_only_on_saved_facts_raises_no_flags():
    letter = (
        "Dear Workforce Development Solutions team,\n\n"
        "In ClearMark I built an image inpainting application with Python, FastAPI and PyTorch, using a Celery and Redis queue.\n\n"
        "For OutreachPulse I used Node.js, TypeScript and PostgreSQL, with AES‑256‑GCM encryption at rest.\n\n"
        "I would like to bring my Python and Java skills to your team. The posting mentions Kubernetes, which would be new to me.\n"
    )

    assert find_unsupported_claims(letter, PROFILE, PROJECTS, JOB) == []


def test_a_technology_attached_to_the_wrong_project_is_flagged():
    letter = "In ClearMark I designed the API with Python and FastAPI, leveraging MongoDB for flexible storage of image metadata."

    claims = find_unsupported_claims(letter, PROFILE, PROJECTS, JOB)

    assert len(claims) == 1 and "MongoDB" in claims[0]["reason"] and "ClearMark" in claims[0]["reason"]
    assert claims[0]["sentence"].startswith("In ClearMark")


def test_work_added_to_a_project_paragraph_is_flagged():
    letter = (
        "I led OutreachPulse, built with Node.js, TypeScript and PostgreSQL. "
        "In parallel, I prototyped a microservice in Java that stores results in MySQL."
    )

    reasons = _reasons(letter)

    assert any("Java" in reason for reason in reasons) and any("MySQL" in reason for reason in reasons)


def test_numbers_and_technologies_absent_from_the_cv_are_flagged():
    letter = "I reduced latency by 35% using Rust and Kafka across 12 microservices.\n\nI have worked since 2025 as a freelancer."

    reasons = " | ".join(_reasons(letter))

    assert "35%" in reasons and "Rust" in reasons and "Kafka" in reasons
    assert "2025" not in reasons  # that year is on the CV


def test_claiming_a_skill_that_only_the_job_posting_mentions_is_flagged():
    letter = "I have hands-on Kubernetes experience from several production clusters."

    claims = find_unsupported_claims(letter, PROFILE, PROJECTS, JOB)

    assert len(claims) == 1 and "Kubernetes" in claims[0]["reason"]


def test_an_empty_letter_or_profile_is_handled():
    assert find_unsupported_claims("", PROFILE, PROJECTS, JOB) == []
    assert find_unsupported_claims("I know Python.", {}, [], {}) != []


def test_invented_contact_details_are_flagged_and_the_company_name_is_not():
    letter = "I am eager to join Workforce Development Solutions.\n\nBest regards,\nAda Example\n+1 (555) 123-4567 | ada@email.com | linkedin.com/in/ada"

    reasons = " | ".join(_reasons(letter))

    assert "+1 (555) 123-4567" in reasons and "ada@email.com" in reasons and "linkedin.com/in/ada" in reasons
    assert "Workforce" not in reasons


def test_general_skill_lists_are_not_judged_against_a_project_named_elsewhere():
    letter = (
        "- In ClearMark I used Python and FastAPI.\n"
        "- Full-stack fluency: I work with Java, MySQL and MongoDB.\n"
    )

    assert find_unsupported_claims(letter, PROFILE, PROJECTS, JOB) == []


def test_a_project_stack_alias_counts():
    projects = [{"title": "LeadScout", "tech_stack": ["Python", "Vanilla JS"], "content": "CLI agent"}]

    assert find_unsupported_claims("LeadScout combines Python and JavaScript.", {"skills": ["Python", "JavaScript"]}, projects, {}) == []



def test_spelling_variants_of_a_cv_term_are_not_flagged():
    profile = {"skills": ["REST APIs", "LLM"], "raw_cv_text": "Built REST APIs and LLM tool-calling workflows."}

    assert find_unsupported_claims("I design RESTful services and work with LLMs daily.", profile, [], {}) == []


def test_a_flagged_draft_is_rewritten_once_and_the_cleaner_version_is_kept(monkeypatch):
    import asyncio

    from backend.app.core import llm_client as llm_module
    from backend.app.modules.apply import agentic_workflow as workflow

    replies = iter([
        "Dear Acme team,\n\nI built billing services in Python and cut costs by 40% using Rust.\n\nBest regards,\nAda Example",
        "Dear Acme team,\n\nI built billing services in Python.\n\nBest regards,\nAda Example",
    ])
    prompts = []

    async def generate_text(system_prompt, user_prompt, **kwargs):
        prompts.append(user_prompt)
        return {"text": next(replies), "provider_used": "Custom (test)", "is_template_fallback": False}

    monkeypatch.setattr(llm_module.llm_client, "generate_text", generate_text)
    monkeypatch.setattr(workflow.application_pipeline.reviewer, "review", lambda **kwargs: {"passed": True, "issues": [], "suggestions": []})
    monkeypatch.setattr(workflow.rag_memory, "search_relevant_context", lambda query, top_k=2: [])

    result = asyncio.run(workflow.application_pipeline.run_pipeline_async(
        {"id": 1, "title": "Backend Developer", "company": "Acme", "description": "Python services"},
        {"full_name": "Ada Example", "skills": ["Python"], "raw_cv_text": "Python developer who built billing services."},
        {},
    ))

    assert "40%" not in result["cover_letter"] and "Rust" not in result["cover_letter"]
    assert result["unsupported_claims"] == [] and result["claims_repaired"] is True
    assert len(prompts) == 2 and "cut costs by 40% using Rust" in prompts[1]
