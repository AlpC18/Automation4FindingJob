"""Candidate profile, RAG memory, and role discovery API."""

import json
import hashlib
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from backend.app.api.profile import encrypt_profile_values, fetch_candidate_profile
from backend.app.core.database import get_db_connection
from backend.app.core.file_scanner import enforce_upload_scan
from backend.app.core.profile_versioning import compare_profile_revisions, ensure_profile_version, list_profile_revisions
from backend.app.core.security_email import is_configured as smtp_is_configured
from backend.app.core.llm_client import llm_client
from backend.app.modules.setup.cv_cleaner import clean_raw_cv_text, convert_to_ats_standard
from backend.app.modules.setup.cv_parser import (
    CVParseError,
    analyze_cv_quality,
    build_local_optimized_cv,
    extract_cv_text,
    extract_profile_fields,
    validate_ai_cv_analysis,
    validate_ai_profile_fields,
    validate_optimized_cv,
)
from backend.app.modules.setup.interview_flow import audit_cv_completeness
from backend.app.modules.setup.rag_engine import rag_memory
from backend.app.modules.setup.role_discovery import role_discovery_engine
from backend.app.modules.setup.stylometry import analyze_stylometry
from backend.app.modules.setup.cv_analysis_history import list_analysis_runs, record_analysis_run

router = APIRouter()


@router.post("/setup/parse_cv")
async def parse_cv_upload(
    response: Response,
    file: UploadFile = File(...),
    use_ai: bool = Form(False),
):
    """Extract CV text and suggested fields in memory; AI processing requires explicit opt-in."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        await file.close()
        raise HTTPException(status_code=413, detail="CV dosyası en fazla 10 MB olabilir.")
    try:
        enforce_upload_scan(content)
    except ValueError as exc:
        await file.close()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        await file.close()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        text, page_count = extract_cv_text(filename, content)
    except CVParseError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    finally:
        await file.close()

    fields = extract_profile_fields(text)
    analysis = None
    optimized_cv_text = build_local_optimized_cv(text, fields)
    ai_used = False
    ai_provider = None
    ai_warning = None
    if use_ai:
        ai_provider = llm_client.get_effective_provider()
        if ai_provider not in {"local_fallback", ""}:
            try:
                extracted = await llm_client.generate_json(
                    system_prompt=(
                        "Extract candidate profile facts from the supplied resume. Return only a JSON object "
                        "with full_name, email, phone, location, target_role, years_of_experience, skills, "
                        "languages, github_url, summary, experience (title, company, period, bullets), and "
                        "education (degree, school, year). Never infer or invent facts. Use empty strings, zero, "
                        "or empty arrays when a fact is not explicitly stated. Preserve names and contact details exactly. "
                        "Also return analysis with strengths (specific evidence-based positive points), gaps "
                        "(useful information absent from this CV), potential_issues (possible errors or inconsistencies; "
                        "do not claim facts are false), and improvements (actionable edits). Each potential issue has "
                        "severity low/medium/high, finding, evidence (short exact excerpt or empty), and recommendation. "
                        "Also return optimized_resume as an ATS-friendly plain-text rewrite, preserving all facts, "
                        "employers, dates, and credentials exactly; never invent numbers or achievements. Keep it "
                        "concise, use clear section headings and bullet points, and retain original meaning. "
                        "Do not invent facts, employers, dates, or credentials. Distinguish missing information from errors."
                    ),
                    user_prompt="Review this resume text and return the requested JSON only.\n\n" + text[:40000],
                    preferred_provider=ai_provider,
                )
                ai_fields = validate_ai_profile_fields(extracted)
                analysis = validate_ai_cv_analysis(extracted.get("analysis"))
                optimized_cv_text = validate_optimized_cv(extracted.get("optimized_resume"))
                if ai_fields:
                    fields.update(ai_fields)
                    confidence = fields.setdefault("confidence", {})
                    for key in ai_fields:
                        confidence[key] = max(float(confidence.get(key, 0)), 0.82)
                ai_used = bool(ai_fields or analysis or optimized_cv_text)
                if not ai_used:
                    ai_warning = "AI sağlayıcısı yanıt üretemedi; yerel CV alan çıkarımı gösteriliyor."
            except Exception:
                # Local suggestions remain available if the optional provider is unavailable.
                ai_used = False
                analysis = None
                ai_warning = "AI analizi şu anda kullanılamıyor; yerel CV alan çıkarımı gösteriliyor."
        else:
            ai_warning = "Yapılandırılmış AI sağlayıcısı bulunamadı; yerel CV alan çıkarımı gösteriliyor."
    quality = analyze_cv_quality(text, fields, page_count)
    analysis_run = record_analysis_run(
        filename=filename,
        content_hash=hashlib.sha256(content).hexdigest(),
        page_count=page_count,
        character_count=len(text),
        ai_requested=use_ai,
        ai_used=ai_used,
        ai_provider=ai_provider if ai_used else None,
        quality=quality,
        analysis=analysis,
    )

    return {
        "analysis_run_id": analysis_run["id"],
        "filename": filename,
        "page_count": page_count,
        "character_count": len(text),
        "text": text,
        "fields": fields,
        "ai_requested": use_ai,
        "ai_used": ai_used,
        "ai_provider": ai_provider if ai_used else None,
        "analysis": analysis,
        "optimized_cv_text": optimized_cv_text,
        "ai_warning": ai_warning,
        "quality": quality,
    }


@router.get("/setup/cv-analysis/history")
def get_cv_analysis_history(limit: int = 20):
    """Return analysis metadata without exposing uploaded CV contents."""
    return {"runs": list_analysis_runs(limit)}


@router.get("/setup/readiness")
def get_profile_readiness():
    profile = fetch_candidate_profile()
    checks = {
        "full_name": bool(profile.get("full_name")),
        "target_role": bool(profile.get("target_role")),
        "contact": bool(profile.get("email")),
        "skills": bool(profile.get("skills")),
        "experience": bool(profile.get("experience") or profile.get("raw_cv_text")),
        "location": bool(profile.get("location") or profile.get("work_preference")),
    }
    labels = {"full_name": "Ad soyad", "target_role": "Hedef rol", "contact": "E-posta", "skills": "Yetenekler", "experience": "CV veya deneyim", "location": "Konum/çalışma tercihi"}
    missing = [labels[key] for key, complete in checks.items() if not complete]
    return {"completion_percent": round((len(checks) - len(missing)) * 100 / len(checks)), "missing": missing, "checks": checks, "ready": not missing}


@router.get("/setup/profile/revisions")
def get_profile_revisions(limit: int = 20):
    return {"revisions": list_profile_revisions(limit)}


@router.get("/setup/profile/revisions/compare")
def compare_profile_revision_versions(from_version: int, to_version: int):
    try:
        return compare_profile_revisions(from_version, to_version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/setup/profile")
def get_profile():
    profile = fetch_candidate_profile()
    if not profile.get("clean_ats_cv_text"):
        profile["clean_ats_cv_text"] = convert_to_ats_standard(profile)
    return {
        "profile": profile,
        "missing_data_interview_questions": audit_cv_completeness(profile),
    }


class FollowUpEmailPreferenceRequest(BaseModel):
    enabled: bool


@router.get("/setup/notification-preferences")
def get_notification_preferences():
    profile = fetch_candidate_profile()
    return {
        "follow_up_email_reminders": bool(profile.get("follow_up_email_reminders", False)),
        "smtp_configured": smtp_is_configured(),
        "recipient_configured": bool(profile.get("email")),
    }


@router.put("/setup/notification-preferences")
def update_notification_preferences(req: FollowUpEmailPreferenceRequest):
    if req.enabled and not smtp_is_configured():
        raise HTTPException(status_code=503, detail="E-posta hatırlatmalarını açmak için SMTP ayarları gerekli.")
    profile = fetch_candidate_profile()
    if req.enabled and not profile.get("email"):
        raise HTTPException(status_code=409, detail="E-posta hatırlatmaları için profiline e-posta adresi eklemelisin.")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        row = cursor.execute("SELECT id FROM candidate_profile ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            raise HTTPException(status_code=409, detail="Önce profilini kaydetmelisin.")
        row_id = row["id"] if isinstance(row, dict) else row[0]
        cursor.execute(
            "UPDATE candidate_profile SET follow_up_email_reminders = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (int(req.enabled), row_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "follow_up_email_reminders": req.enabled,
        "smtp_configured": smtp_is_configured(),
        "recipient_configured": bool(profile.get("email")),
    }


class ProfileUpdateRequest(BaseModel):
    full_name: str
    email: str
    target_role: str
    target_categories: Optional[List[str]] = None
    target_roles: Optional[List[str]] = None
    years_of_experience: int
    skills: List[str]
    raw_cv_text: Optional[str] = ""
    phone: Optional[str] = ""
    location: Optional[str] = ""
    work_preference: Optional[str] = ""
    languages: List[str] = Field(default_factory=list)
    github_url: Optional[str] = ""
    summary: Optional[str] = ""
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    work_style: Optional[str] = ""
    writing_tone: Optional[str] = ""


@router.post("/setup/update_profile")
def update_profile(req: ProfileUpdateRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    values = encrypt_profile_values((
        req.full_name, req.email, req.phone, req.location, req.target_role,
        req.years_of_experience, json.dumps(req.skills), json.dumps(req.experience),
        json.dumps(req.education), req.raw_cv_text or "",
        clean_raw_cv_text(req.raw_cv_text or ""), req.work_preference or "",
        json.dumps(req.languages), req.github_url or "", req.summary or "",
        req.work_style or "", req.writing_tone or "",
    ))
    cursor.execute("SELECT id, target_role, target_categories_json, target_roles_json FROM candidate_profile ORDER BY id DESC LIMIT 1")
    existing = cursor.fetchone()
    existing_value = (lambda key, index: existing[key] if isinstance(existing, dict) else existing[index])
    existing_categories = json.loads((existing_value("target_categories_json", 2) or "[]")) if existing else []
    existing_roles = json.loads((existing_value("target_roles_json", 3) or "[]")) if existing else []
    categories_json = json.dumps(req.target_categories if req.target_categories is not None else existing_categories)
    previous_target_role = existing_value("target_role", 1) if existing else ""
    roles = req.target_roles if req.target_roles is not None else (
        existing_roles if req.target_role == previous_target_role else ([req.target_role] if req.target_role else [])
    )
    if not roles and req.target_role and req.target_roles is not None:
        roles = [req.target_role]
    roles_json = json.dumps(roles)
    if existing:
        cursor.execute(
            """
            UPDATE candidate_profile SET
                full_name = ?, email = ?, phone = ?, location = ?, target_role = ?,
                years_of_experience = ?, skills_json = ?, experience_json = ?,
                education_json = ?, raw_cv_text = ?, clean_ats_cv_text = ?,
                work_preference = ?, languages_json = ?, github_url = ?, summary = ?,
                work_style = ?, writing_tone = ?, target_categories_json = ?, target_roles_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (*values, categories_json, roles_json, existing["id"] if isinstance(existing, dict) else existing[0]),
        )
    else:
        cursor.execute(
            """
            INSERT INTO candidate_profile (
                full_name, email, phone, location, target_role, years_of_experience,
                skills_json, experience_json, education_json, raw_cv_text,
                clean_ats_cv_text, work_preference, languages_json, github_url,
                summary, work_style, writing_tone, target_categories_json, target_roles_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*values, categories_json, roles_json),
        )
    conn.commit()
    conn.close()
    profile = fetch_candidate_profile()
    version = ensure_profile_version(profile)
    return {"status": "SUCCESS", "message": "Profile updated and ATS standardized", "profile_version": version}


class StylometryRequest(BaseModel):
    writing_samples: List[str]


@router.post("/setup/stylometry")
def generate_stylometry_profile(req: StylometryRequest):
    result = analyze_stylometry(req.writing_samples)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE candidate_profile SET style_profile_json = ?
        WHERE id = (SELECT id FROM candidate_profile ORDER BY id DESC LIMIT 1)
        """,
        (encrypt_profile_values((json.dumps(result),))[0],),
    )
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "style_profile": result}


@router.get("/setup/rag_projects")
def get_rag_projects():
    return {"projects": rag_memory.documents}


class AddProjectRequest(BaseModel):
    title: str
    content: str
    tech_stack: List[str]
    metrics: str = ""
    category: str = "Engineering"


@router.post("/setup/rag_projects")
def add_rag_project(req: AddProjectRequest):
    return {
        "status": "SUCCESS",
        "project": rag_memory.add_project(req.title, req.content, req.tech_stack, req.metrics, req.category),
    }


@router.get("/setup/discovered_roles")
@router.get("/api/setup/discovered_roles")
def get_discovered_roles():
    profile = fetch_candidate_profile()
    return {
        "candidate_name": profile.get("full_name"),
        "target_role": profile.get("target_role"),
        "roles": role_discovery_engine.discover_eligible_roles(profile),
        "location_presets": role_discovery_engine.get_work_style_presets(),
    }
