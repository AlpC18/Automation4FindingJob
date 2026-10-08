"""Application material generation and outreach endpoints."""

import json
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.app.api.profile import fetch_candidate_profile
from backend.app.core.database import get_db_connection
from backend.app.core.profile_versioning import ensure_profile_version
from backend.app.core.security import decrypt_secret, encrypt_secret
from backend.app.core.event_logger import agent_logger
from backend.app.core.llm_client import is_template_engine
from backend.app.modules.apply.agentic_workflow import application_pipeline
from backend.app.modules.apply.cv_tailoring import build_tailored_resume_profile
from backend.app.modules.apply.cultural_engine import cultural_engine
from backend.app.modules.apply.decision_maker import decision_maker_engine
from backend.app.modules.apply.fit_report import build_fit_report, tailored_cv_profile
from backend.app.modules.apply.form_automator import form_automator
import urllib.parse
from backend.app.modules.setup.rag_engine import rag_memory
from backend.app.modules.setup.pdf_generator import ats_pdf_generator
from backend.app.modules.outcome.follow_up_cadence import follow_up_cadence_engine


router = APIRouter()


class ApplyPackageRequest(BaseModel):
    job_id: str
    provider: Optional[str] = None


@router.post("/apply/generate_package")
async def generate_application_package(req: ApplyPackageRequest):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scraped_jobs WHERE id = ?", (req.job_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")

        job_data = dict(row)
        profile = fetch_candidate_profile()
        profile_version = ensure_profile_version(profile)
        tailored_result = build_tailored_resume_profile(profile, job_data)
        # Bullets come ranked for the posting; the summary line, skill order and projects come from the fit report.
        tailored_profile = tailored_cv_profile(tailored_result["profile"], rag_memory.documents, job_data)
        style_profile = {
            **profile.get("style_profile", {}),
            "writing_tone": profile.get("writing_tone", ""),
            "work_style": profile.get("work_style", ""),
        }

        pipeline_res = await application_pipeline.run_pipeline_async(
            job_data=job_data,
            candidate_profile=profile,
            style_profile=style_profile,
            preferred_provider=req.provider,
        )

        xray_dork = decision_maker_engine.generate_xray_dork(
            job_data["company"], job_data.get("location", "Remote")
        )
        rag_first_proj = pipeline_res["rag_context_used"][0] if pipeline_res["rag_context_used"] else None
        cold_dm = decision_maker_engine.draft_three_sentence_outreach(
            job_data["company"], job_data["title"], profile, rag_first_proj
        )
        micro_port = decision_maker_engine.synthesize_micro_portfolio(
            job_data["title"], job_data["company"], pipeline_res["rag_context_used"]
        )

        tailoring = tailored_result["tailoring"]
        provider_used = pipeline_res.get("provider_used", "Auto")
        cursor.execute(
            """
            UPDATE scraped_jobs
            SET cover_letter = ?,
                human_texture_score = ?,
                micro_portfolio = ?,
                cold_outreach_dork = ?,
                cold_outreach_msg = ?,
                draft_source = ?,
                status = 'Human Review'
            WHERE id = ?
            """,
            (
                pipeline_res["cover_letter"],
                pipeline_res["human_texture_score"],
                micro_port,
                xray_dork,
                cold_dm,
                provider_used,
                req.job_id,
            ),
        )
        package_id = uuid.uuid4().hex
        cursor.execute("""INSERT INTO application_packages
            (id, job_id, profile_version, cover_letter, tailoring_json, tailored_profile_json)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (package_id, req.job_id, profile_version, pipeline_res["cover_letter"], json.dumps(tailoring),
             encrypt_secret(json.dumps(tailored_profile))))
        cursor.execute("""INSERT INTO application_attribution(job_id, profile_version, target_role, platform)
            VALUES (?, ?, ?, ?) ON CONFLICT(job_id) DO UPDATE SET profile_version=excluded.profile_version,
            target_role=excluded.target_role, platform=excluded.platform, updated_at=CURRENT_TIMESTAMP""",
            (req.job_id, profile_version, profile.get("target_role") or job_data.get("title", ""), job_data.get("platform", "")))
        conn.commit()
    finally:
        conn.close()

    return {
        "job_id": req.job_id,
        "package_id": package_id,
        "profile_version": profile_version,
        "cover_letter": pipeline_res["cover_letter"],
        "human_texture_score": pipeline_res["human_texture_score"],
        "is_human_verified": pipeline_res["is_human_verified"],
        "metrics": pipeline_res["metrics"],
        "qa_audit_log": pipeline_res["qa_audit_log"],
        "provider_used": provider_used,
        "is_template_fallback": is_template_engine(provider_used),
        "micro_portfolio": micro_port,
        "cold_outreach": {"xray_dork": xray_dork, "cold_dm_3_sentence": cold_dm},
        "tailoring": tailoring,
        "tailored_cv": {
            "full_name": tailored_profile.get("full_name", ""),
            "summary": tailored_profile.get("summary", ""),
            "skills": tailored_profile.get("skills", []),
            "experience": tailored_profile.get("experience", []),
            "education": tailored_profile.get("education", []),
            "facts_rewritten": False,
            "package_id": package_id,
        },
        "requires_user_review": True,
    }


def _tailored_cv_pdf(package_id: str, theme: str):
    conn = get_db_connection()
    try:
        row = conn.cursor().execute(
            "SELECT tailored_profile_json FROM application_packages WHERE id = ?", (package_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Tailored resume package not found.")
    encrypted_profile = row["tailored_profile_json"] if isinstance(row, dict) else row[0]
    if not encrypted_profile:
        raise HTTPException(status_code=404, detail="Tailored resume is not available for this package.")
    try:
        profile = json.loads(decrypt_secret(encrypted_profile))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Could not read the tailored resume package.") from exc
    return ats_pdf_generator.generate_cv_pdf(profile, theme=theme)


@router.get("/apply/preview_tailored_cv")
def preview_tailored_cv(package_id: str, theme: str = "navy"):
    pdf_buffer = _tailored_cv_pdf(package_id, theme)
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="Tailored_Resume.pdf"'},
    )


@router.get("/apply/download_tailored_cv")
def download_tailored_cv(package_id: str, theme: str = "navy"):
    pdf_buffer = _tailored_cv_pdf(package_id, theme)
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="Tailored_Resume.pdf"'},
    )


class FormAnswerRequest(BaseModel):
    question: str


@router.post("/apply/form_answer")
def answer_form_question(req: FormAnswerRequest):
    return form_automator.answer_question(req.question, fetch_candidate_profile())


class SaveFormMemoryRequest(BaseModel):
    question: str
    answer: str


@router.post("/apply/save_form_memory")
def save_form_memory(req: SaveFormMemoryRequest):
    form_automator.save_human_answer_to_memory(req.question, req.answer)
    return {"status": "SUCCESS", "message": "Answer persisted in Form Memory"}


@router.get("/setup/download_ats_cv")
def download_ats_cv(theme: str = "navy"):
    pdf_buffer = ats_pdf_generator.generate_cv_pdf(fetch_candidate_profile(), theme=theme)
    agent_logger.log_event("PDF_ENGINE", f"Generated ATS-compliant CV PDF (Theme: {theme}).")
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="ATS_Clean_Resume.pdf"'},
    )


@router.get("/setup/preview_ats_cv")
def preview_ats_cv(theme: str = "navy"):
    pdf_buffer = ats_pdf_generator.generate_cv_pdf(fetch_candidate_profile(), theme=theme)
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="ATS_Clean_Resume.pdf"'},
    )


def _cover_letter_pdf(job_id: str, theme: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scraped_jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if not row or not row["cover_letter"]:
        raise HTTPException(status_code=404, detail="Cover letter not found for this job.")

    profile = fetch_candidate_profile()
    return row, ats_pdf_generator.generate_cover_letter_pdf(
        job_title=row["title"],
        company=row["company"],
        cover_letter_text=row["cover_letter"],
        candidate_name=profile.get("full_name", "Candidate"),
        theme=theme,
    )


@router.get("/apply/download_cover_letter_pdf")
def download_cover_letter_pdf(job_id: str, theme: str = "navy"):
    row, pdf_buffer = _cover_letter_pdf(job_id, theme)
    agent_logger.log_event("PDF_ENGINE", f"Generated Cover Letter PDF for {row['company']}.")
    filename = row["company"].replace(" ", "_")
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Cover_Letter_{filename}.pdf"'},
    )


@router.get("/apply/preview_cover_letter_pdf")
def preview_cover_letter_pdf(job_id: str, theme: str = "navy"):
    row, pdf_buffer = _cover_letter_pdf(job_id, theme)
    filename = row["company"].replace(" ", "_")
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="Cover_Letter_{filename}.pdf"'},
    )


class MultilingualRequest(BaseModel):
    culture_code: str
    job_id: str


@router.post("/apply/multilingual")
def adapt_culture_language(req: MultilingualRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scraped_jobs WHERE id = ?", (req.job_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found.")

    profile = fetch_candidate_profile()
    res = cultural_engine.adapt_application_materials(
        culture_code=req.culture_code,
        job_title=row["title"],
        company=row["company"],
        candidate_name=profile.get("full_name", "Candidate"),
        top_skills=profile.get("skills") or [],
        rag_metrics="",
    )
    agent_logger.log_event("CULTURAL_ENGINE", f"Adapted text to {res['culture_label']}.")
    return res


@router.get("/apply/fit_report/{job_id}")
def get_fit_report(job_id: str):
    """How this posting and the saved CV line up, and what to change for this one application."""
    conn = get_db_connection()
    try:
        row = conn.cursor().execute("SELECT * FROM scraped_jobs WHERE id = ?", (job_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found.")
    return build_fit_report(fetch_candidate_profile(), rag_memory.documents, dict(row))


@router.get("/apply/fit_report/{job_id}/cv.pdf")
def download_fit_tailored_cv(job_id: str, theme: str = "navy"):
    """The CV as a PDF arranged for this posting: its summary line, skill order and most relevant projects."""
    conn = get_db_connection()
    try:
        row = conn.cursor().execute("SELECT * FROM scraped_jobs WHERE id = ?", (job_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found.")
    job = dict(row)
    tailored = tailored_cv_profile(build_tailored_resume_profile(fetch_candidate_profile(), job)["profile"], rag_memory.documents, job)
    company = "".join(char for char in str(job.get("company") or "job") if char.isalnum() or char in "-_ ").strip().replace(" ", "_") or "job"
    return Response(
        content=ats_pdf_generator.generate_cv_pdf(tailored, theme=theme).getvalue(), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="CV_{company}.pdf"', "Cache-Control": "no-store"},
    )


class EmailApplicationRequest(BaseModel):
    job_id: str
    recipient_email: str
    subject: str
    body: str
    attach_cv: bool = True


@router.post("/apply/send_email_application")
def send_email_application(req: EmailApplicationRequest):
    recipient = (req.recipient_email or "").strip()
    if not recipient or "@" not in recipient:
        raise HTTPException(status_code=422, detail="Geçerli bir alıcı e-posta adresi giriniz.")

    from backend.app.core.smtp_credentials import get_smtp_configuration
    smtp_config = get_smtp_configuration()
    if not smtp_config.get("host") or not smtp_config.get("from_email"):
        raise HTTPException(status_code=503, detail="E-posta göndermek için lütfen önce Ayarlar sayfasından SMTP / E-posta sunucu bilgilerinizi kaydedin.")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scraped_jobs WHERE id = ?", (req.job_id,))
        job_row = cursor.fetchone()
        if not job_row:
            raise HTTPException(status_code=404, detail="İlan bulunamadı.")
        job = dict(job_row)

        profile = fetch_candidate_profile()

        # Prepare EmailMessage
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = req.subject or f"İş Başvurusu: {job['title']} - {profile.get('full_name', '')}"
        msg["From"] = smtp_config["from_email"]
        msg["To"] = recipient
        msg.set_content(req.body)

        if req.attach_cv:
            try:
                tailored = tailored_cv_profile(
                    build_tailored_resume_profile(profile, job)["profile"],
                    rag_memory.documents,
                    job,
                )
                pdf_bytes = ats_pdf_generator.generate_cv_pdf(tailored, theme="navy").getvalue()
                candidate_name = (profile.get("full_name") or "Aday").replace(" ", "_")
                msg.add_attachment(
                    pdf_bytes,
                    maintype="application",
                    subtype="pdf",
                    filename=f"CV_{candidate_name}.pdf",
                )
            except Exception as e:
                agent_logger.log_event("EMAIL_APPLY", f"Could not attach PDF CV: {e}")

        # Send via SMTP
        with smtplib.SMTP(smtp_config["host"], smtp_config["port"], timeout=20) as server:
            if smtp_config.get("use_tls", True):
                server.starttls()
            if smtp_config.get("username"):
                server.login(smtp_config["username"], smtp_config["password"])
            server.send_message(msg)

        # Update job status to Applied
        cursor.execute(
            """UPDATE scraped_jobs SET
                status = 'Applied',
                applied_at = CURRENT_TIMESTAMP,
                submission_state = 'submitted',
                submission_confirmed = 1,
                submission_message = ?
            WHERE id = ?""",
            (f"E-posta ile gönderildi: {recipient}", req.job_id),
        )

        # Record to application_status_history
        cursor.execute(
            """INSERT INTO application_status_history (
                id, job_id, from_status, to_status, source, note
            ) VALUES (?, ?, ?, 'Applied', 'email_apply', ?)""",
            (
                f"hist-{uuid.uuid4().hex[:8]}",
                req.job_id,
                job.get("status") or "Draft",
                f"E-posta gönderildi: {recipient}. Konu: {req.subject}",
            ),
        )
        conn.commit()

        agent_logger.log_event("EMAIL_APPLY", f"Successfully sent application email to {recipient} for job {req.job_id}")
        return {
            "status": "SUCCESS",
            "message": f"{recipient} adresine başvuru e-postanız ve özgeçmişiniz başarıyla iletildi!",
            "job_id": req.job_id,
        }
    except HTTPException:
        raise
    except Exception as exc:
        agent_logger.log_event("EMAIL_APPLY", f"SMTP delivery failed: {exc}")
        raise HTTPException(status_code=500, detail=f"E-posta gönderilemedi: {str(exc)}") from exc
    finally:
        conn.close()


@router.get("/apply/jobs/{job_id}/tailored_cv_pdf")
def get_job_tailored_cv_pdf(job_id: str, theme: str = "navy"):
    """Download a targeted 1-page ATS-optimized PDF CV specifically tailored to this job."""
    return download_fit_tailored_cv(job_id=job_id, theme=theme)


class OutreachDraftRequest(BaseModel):
    job_id: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = "Remote"


@router.post("/apply/outreach/draft")
def generate_outreach_draft(req: OutreachDraftRequest):
    """
    Generate Google X-Ray Dork link, 3-sentence hiring manager outreach,
    and micro-case study for strategic cold application.
    """
    company = req.company or ""
    title = req.title or ""
    location = req.location or "Remote"

    if req.job_id:
        conn = get_db_connection()
        try:
            row = conn.cursor().execute("SELECT company, title, location FROM scraped_jobs WHERE id = ?", (req.job_id,)).fetchone()
            if row:
                company = row["company"] or company
                title = row["title"] or title
                location = row["location"] or location
        finally:
            conn.close()

    if not company:
        raise HTTPException(status_code=400, detail="Şirket adı belirtilmelidir.")

    profile = fetch_candidate_profile()
    dork_query = decision_maker_engine.generate_xray_dork(company, location)
    google_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(dork_query)}"

    # Get primary project from memory
    from backend.app.modules.setup.rag_engine import rag_memory
    primary_project = rag_memory.documents[0] if rag_memory.documents else None

    cold_msg = decision_maker_engine.draft_three_sentence_outreach(
        company_name=company,
        job_title=title or "Açık Pozisyon",
        candidate_profile=profile,
        rag_project=primary_project,
    )

    micro_portfolio = decision_maker_engine.synthesize_micro_portfolio(
        job_title=title or "Pozisyon",
        company=company,
        rag_projects=rag_memory.documents,
    )

    # Predicted email patterns for domain
    clean_domain = company.lower().replace(" ", "").replace(",", "").replace(".", "") + ".com"
    email_patterns = [
        f"ad.soyad@{clean_domain}",
        f"ad@{clean_domain}",
        f"hr@{clean_domain}",
        f"careers@{clean_domain}",
    ]

    return {
        "company": company,
        "title": title,
        "location": location,
        "dork_query": dork_query,
        "google_search_url": google_url,
        "cold_outreach_message": cold_msg,
        "micro_portfolio": micro_portfolio,
        "predicted_email_formats": email_patterns,
    }


@router.get("/apply/jobs/{job_id}/follow_up_cadence")
def get_job_follow_up_cadence(job_id: str):
    """Generate 3-stage follow-up cadence messages (Touch 1, Touch 2, Touch 3)."""
    conn = get_db_connection()
    try:
        row = conn.cursor().execute("SELECT company, title FROM scraped_jobs WHERE id = ?", (job_id,)).fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Job not found.")

    company = row["company"] or "Şirket"
    title = row["title"] or "Pozisyon"
    cadence = follow_up_cadence_engine.generate_cadence_messages(company, title)
    return cadence



