"""
Unit & Integration Tests for New Enhancements
Covers:
1. ATS PDF Generation (CV & Cover Letter)
2. Multilingual Cultural Adaptation (Albanian, Turkish, Global English)
3. Decision Maker Email Finder & Domain Inference
4. Playwright Stealth Worker Execution
5. Real-time Agent Event Logger
6. Multi-LLM Provider Engine
"""

import pytest
from backend.app.modules.setup.pdf_generator import ats_pdf_generator
from backend.app.modules.apply.cultural_engine import cultural_engine
from backend.app.modules.apply.email_finder import email_finder
from backend.app.modules.scrape.stealth_browser import stealth_worker
from backend.app.core.event_logger import agent_logger
from backend.app.core.llm_client import llm_client
from backend.app.core.config import settings

def test_ats_pdf_generation():
    profile = {
        "full_name": "Alperen Cihan",
        "email": "alperen@example.com",
        "phone": "+90 555 123 4567",
        "skills": ["Python", "FastAPI", "Next.js"],
        "experience": [{"title": "AI Engineer", "company": "Tech Corp", "period": "2023 - Present", "bullets": ["Built RAG pipeline"]}]
    }
    pdf_buf = ats_pdf_generator.generate_cv_pdf(profile)
    pdf_bytes = pdf_buf.getvalue()
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")

def test_cover_letter_pdf_generation():
    pdf_buf = ats_pdf_generator.generate_cover_letter_pdf(
        job_title="Lead AI Engineer",
        company="Cognitive Scale AI",
        cover_letter_text="Hi team,\n\nI am writing regarding the role.",
        candidate_name="Alperen Cihan"
    )
    pdf_bytes = pdf_buf.getvalue()
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")

def test_multilingual_cultural_adaptation():
    sq_res = cultural_engine.adapt_application_materials(
        culture_code="kosovo_sq",
        job_title="Full Stack Developer",
        company="Gjirafa Labs",
        candidate_name="Alperen Cihan",
        top_skills=["Next.js", "Python"]
    )
    assert "I nderuar ekipi" in sq_res["cover_letter"]
    assert "Shqip" in sq_res["culture_label"]

    tr_res = cultural_engine.adapt_application_materials(
        culture_code="turkey_tr",
        job_title="AI Engineer",
        company="Trendyol",
        candidate_name="Alperen Cihan",
        top_skills=["Python", "LangChain"]
    )
    assert "Merhaba" in tr_res["cover_letter"]
    assert "Türkçe" in tr_res["culture_label"]

def test_outreach_never_reports_simulated_success_without_smtp(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "")
    result = email_finder.send_smtp_outreach("person@example.test", "Hello", "A message")
    assert result["status"] == "NOT_CONFIGURED"
    assert "gönderilmedi" in result["message"]


def test_outreach_uses_real_smtp_adapter_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(settings, "SMTP_USER", "sender@example.test")
    monkeypatch.setattr(settings, "SMTP_PASS", "test-app-password")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "sender@example.test")
    sent = []
    monkeypatch.setattr("backend.app.modules.apply.email_finder.send_security_email", lambda *args: sent.append(args))
    result = email_finder.send_smtp_outreach("person@example.test", "Hello", "A message")
    assert result["status"] == "SENT"
    assert sent == [("person@example.test", "Hello", "A message")]


def test_smtp_failure_does_not_leak_server_details(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(settings, "SMTP_USER", "sender@example.test")
    monkeypatch.setattr(settings, "SMTP_PASS", "test-app-password")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "sender@example.test")

    def fail_smtp(*_args):
        raise RuntimeError("smtp-password=private-value")

    monkeypatch.setattr("backend.app.modules.apply.email_finder.send_security_email", fail_smtp)
    result = email_finder.send_smtp_outreach("person@example.test", "Hello", "A message")
    assert result["status"] == "FAILED"
    assert "private-value" not in str(result)

@pytest.mark.asyncio
async def test_stealth_browser_worker():
    res = await stealth_worker.execute_easy_apply_flow(
        job_url="https://www.linkedin.com/jobs",
        applicant_data={"full_name": "Alperen Cihan"},
        headless=True
    )
    # The worker inspects the form only; an explicit submission workflow must
    # never report a successful application without confirmation.
    assert res["applied"] is False
    assert res["submission_confirmed"] is False
    assert res["status"] == "DISABLED"  # LinkedIn automation is opt-in

def test_agent_event_logger():
    agent_logger.log_event("TEST", "Verification event logged.")
    logs = agent_logger.get_recent_logs()
    assert len(logs) > 0
    assert any(l["module"] == "TEST" for l in logs)

@pytest.mark.asyncio
async def test_multi_llm_client_fallback():
    res = await llm_client.generate_text(
        system_prompt="You are a career assistant.",
        user_prompt="Write a brief note.",
        preferred_provider="auto"
    )
    assert len(res["text"]) > 20
    assert res["human_texture_score"] >= 80.0
    assert res["is_human_verified"] is True

def test_llm_providers_status_and_switching():
    status = llm_client.get_providers_status()
    assert "providers" in status
    provider_ids = [p["id"] for p in status["providers"]]
    assert "openai" in provider_ids
    assert "gemini" in provider_ids
    assert "anthropic" in provider_ids
    assert "deepseek" in provider_ids
    assert "ollama" in provider_ids
    assert "local_fallback" in provider_ids

    # Test dynamic provider switching
    llm_client.set_active_provider("deepseek", "deepseek-coder")
    assert llm_client.provider == "deepseek"
    assert llm_client.custom_model == "deepseek-coder"
    # Reset to auto
    llm_client.set_active_provider("auto", None)

@pytest.mark.asyncio
async def test_llm_connection_ping():
    res = await llm_client.test_provider_connection("local_fallback")
    assert res["status"] == "SUCCESS"
    assert "latency_ms" in res

def test_ats_pdf_themes_and_xml_safety():
    # Profile with symbols that would break unescaped XML parsers: &, <, >, quotes
    special_profile = {
        "full_name": "Alperen Cihan & Partners",
        "email": "alp<test>@example.com",
        "phone": "+90 555 123 4567",
        "skills": ["C++", "R&D Algorithms", "Latency < 50ms"],
        "experience": [
            {
                "title": "Lead Software & R&D Architect",
                "company": "Scale & Grow Inc.",
                "period": "2022 - Present",
                "bullets": ["Optimized throughput > 500 req/sec & reduced overhead < 20%"]
            }
        ],
        "projects": [
            {
                "title": "Autonomous R&D Cluster",
                "tech_stack": ["FastAPI", "C++", "Docker"],
                "metric": "Latency < 10ms"
            }
        ]
    }
    # Test all themes
    for theme in ["navy", "charcoal", "slate", "emerald"]:
        buf = ats_pdf_generator.generate_cv_pdf(special_profile, theme=theme)
        pdf_bytes = buf.getvalue()
        assert len(pdf_bytes) > 500
        assert pdf_bytes.startswith(b"%PDF")

    cl_buf = ats_pdf_generator.generate_cover_letter_pdf(
        job_title="R&D <Systems> Engineer",
        company="AT&T & Tech",
        cover_letter_text="Hi team,\n\nI have handled systems with <10ms latency & >99.9% uptime.",
        candidate_name="Alperen Cihan",
        theme="emerald"
    )
    assert cl_buf.getvalue().startswith(b"%PDF")

@pytest.mark.asyncio
async def test_inbox_email_classification_and_scheduling():
    from backend.app.modules.outcome.inbox_agent import inbox_agent
    
    # 1. Interview invite email
    invite_res = await inbox_agent.ingest_incoming_email(
        sender_email="recruiter@stripe.com",
        sender_name="Stripe Talent",
        subject="Interview Invitation: Next Steps for Senior AI Engineer",
        body_text="Hi Alperen, We loved your background and would love to schedule a call: https://meet.google.com/abc-defg-hij"
    )
    assert invite_res["classification"] == "INTERVIEW_INVITE"
    assert invite_res["meet_link"] == "https://meet.google.com/abc-defg-hij"
    assert "CET" in invite_res["proposed_reply"]

    # 2. Rejection email
    rejection_res = await inbox_agent.ingest_incoming_email(
        sender_email="hr@amazon.com",
        sender_name="Amazon HR",
        subject="Application Update for Software Engineer",
        body_text="Unfortunately, we have decided to move forward with other candidates at this time."
    )
    assert rejection_res["classification"] == "REJECTION"

def test_on_the_fly_job_analyzer(monkeypatch):
    from backend.app.core.config import settings

    monkeypatch.setattr(settings, "DEMO_DATA_ENABLED", True)
    monkeypatch.setattr(
        "backend.app.api.routers.scrape.fetch_candidate_profile",
        lambda: {"skills": ["Python", "FastAPI", "Docker"], "years_of_experience": 4},
    )
    from backend.app.api.router import analyze_job_on_the_fly, AnalyzeOnTheFlyRequest
    req = AnalyzeOnTheFlyRequest(
        title="Senior Python & AI Engineer",
        company="Datadog",
        description="Looking for Python, FastAPI, Docker, and distributed systems experience.",
        location="Remote"
    )
    result = analyze_job_on_the_fly(req)
    assert result["match_score"] > 60
    assert "match_tier" in result
