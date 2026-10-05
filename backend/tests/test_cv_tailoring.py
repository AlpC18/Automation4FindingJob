import asyncio
import json

import pytest

from backend.app.api.profile import encrypt_profile_values
from backend.app.core.config import settings
from backend.app.core.database import get_db_connection, init_auth_db, init_db, init_tenant_db, use_tenant
from backend.app.modules.apply.cv_tailoring import build_tailored_resume_profile


@pytest.fixture
def isolated_database(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATA_PATH", tmp_path)
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'control.db'}")
    monkeypatch.setattr(settings, "MULTI_TENANT_ENABLED", True)
    init_db()
    init_auth_db()
    return tmp_path


def test_tailoring_prioritizes_only_candidate_facts_and_keeps_source_unchanged():
    source = {
        "full_name": "Ada Candidate",
        "summary": "Backend engineer with production API experience.",
        "skills": ["Excel", "Python", "FastAPI", "Figma"],
        "experience": [
            {
                "title": "Backend Engineer",
                "company": "Example Co",
                "period": "2022–2024",
                "bullets": ["Maintained internal dashboards", "Built Python APIs with FastAPI"],
            }
        ],
        "education": [{"degree": "BSc Computer Science", "school": "Example University", "year": "2022"}],
    }
    original = {
        **source,
        "skills": list(source["skills"]),
        "experience": [{**source["experience"][0], "bullets": list(source["experience"][0]["bullets"])}],
    }

    result = build_tailored_resume_profile(source, {
        "title": "Python Backend Engineer",
        "description": "Build and maintain Python APIs using FastAPI.",
        "platform": "test",
        "skill_gaps": {"missing_skills": ["Kubernetes"]},
    })

    tailored = result["profile"]
    assert tailored["skills"][:2] == ["Python", "FastAPI"]
    assert tailored["experience"][0]["bullets"][0] == "Built Python APIs with FastAPI"
    assert tailored["experience"][0]["period"] == "2022–2024"
    assert tailored["summary"] == source["summary"]
    assert result["tailoring"]["gaps_to_address_honestly"] == ["Kubernetes"]
    assert result["tailoring"]["facts_rewritten"] is False
    assert source == original


def test_application_package_persists_encrypted_tailored_cv_and_renders_pdf(isolated_database, monkeypatch):
    from backend.app.api.routers import application

    tenant_id = "tailored-package"
    init_tenant_db(tenant_id)
    with use_tenant(tenant_id):
        conn = get_db_connection()
        try:
            conn.cursor().execute(
                """INSERT INTO candidate_profile
                   (full_name, email, target_role, years_of_experience, skills_json, experience_json,
                    education_json, summary, phone, location, github_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                encrypt_profile_values((
                    "Ada Candidate", "ada@example.test", "Backend Engineer", 4,
                    json.dumps(["Excel", "Python", "FastAPI"]),
                    json.dumps([{"title": "Backend Engineer", "company": "Example Co", "period": "2022–2024", "bullets": ["Built Python APIs with FastAPI", "Maintained Excel reports"]}]),
                    json.dumps([{"degree": "BSc", "school": "Example University", "year": "2022"}]),
                    "Backend engineer with production API experience.", "+1 555 0100", "Berlin", "https://github.com/ada",
                )),
            )
            conn.cursor().execute(
                "INSERT INTO scraped_jobs (id, title, company, platform, description, skill_gaps) VALUES (?, ?, ?, ?, ?, ?)",
                ("tailored-job", "Python Backend Engineer", "Example Co", "test", "Build Python APIs using FastAPI", '{"missing_skills":["Kubernetes"]}'),
            )
            conn.commit()
        finally:
            conn.close()

        async def fake_pipeline(**_kwargs):
            return {
                "cover_letter": "A truthful cover letter draft.", "human_texture_score": 90,
                "rag_context_used": [], "is_human_verified": False,
                "metrics": {}, "qa_audit_log": [], "provider_used": "local_test",
            }

        monkeypatch.setattr(application.application_pipeline, "run_pipeline_async", fake_pipeline)
        monkeypatch.setattr(application.decision_maker_engine, "generate_xray_dork", lambda *_args: "query")
        monkeypatch.setattr(application.decision_maker_engine, "draft_three_sentence_outreach", lambda *_args: "draft")
        monkeypatch.setattr(application.decision_maker_engine, "synthesize_micro_portfolio", lambda *_args: "")

        result = asyncio.run(application.generate_application_package(application.ApplyPackageRequest(job_id="tailored-job")))
        assert result["tailored_cv"]["skills"] == ["Python", "FastAPI", "Excel"]
        assert result["tailored_cv"]["facts_rewritten"] is False
        assert result["tailoring"]["gaps_to_address_honestly"] == ["Kubernetes"]

        conn = get_db_connection()
        try:
            stored = conn.cursor().execute(
                "SELECT tailored_profile_json FROM application_packages WHERE id = ?", (result["package_id"],)
            ).fetchone()["tailored_profile_json"]
        finally:
            conn.close()
        assert "ada@example.test" not in stored
        assert stored.startswith("fernet$")

        pdf = application.preview_tailored_cv(result["package_id"], "slate")
        assert pdf.media_type == "application/pdf"
        assert pdf.body.startswith(b"%PDF-")
