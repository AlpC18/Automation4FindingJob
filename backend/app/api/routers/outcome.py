"""Application lifecycle, Kanban, analytics, and verified submission API."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.modules.outcome.kanban_manager import kanban_manager
from backend.app.modules.outcome.analytics_engine import calculate_funnel_metrics
from backend.app.modules.outcome.follow_up_scheduler import get_pending_follow_ups
from backend.app.api.profile import fetch_candidate_profile
from backend.app.core.database import get_db_connection
from backend.app.core.profile_versioning import ensure_profile_version
from backend.app.modules.outcome.job_workspace import list_status_history, record_status_transition
from backend.app.modules.outcome.today import get_today_actions

router = APIRouter()


@router.get("/outcome/kanban")
def get_kanban_pipeline():
    return kanban_manager.get_kanban_board()


class UpdateStatusRequest(BaseModel):
    job_id: str
    new_status: str
    final_cover_letter: Optional[str] = None


@router.post("/outcome/update_status")
def update_kanban_status(req: UpdateStatusRequest):
    try:
        conn = get_db_connection()
        try:
            previous = conn.cursor().execute("SELECT status FROM scraped_jobs WHERE id = ?", (req.job_id,)).fetchone()
        finally:
            conn.close()
        if req.new_status == "Applied" and req.final_cover_letter:
            result = kanban_manager.approve_human_in_the_loop(req.job_id, req.final_cover_letter)
        else:
            result = kanban_manager.update_job_status(req.job_id, req.new_status)
        record_status_transition(
            req.job_id,
            previous["status"] if previous else None,
            req.new_status,
            note="Kanban aşaması güncellendi.",
        )
        if req.new_status in {"Applied", "Interview", "Offer", "Rejected"}:
            profile = fetch_candidate_profile()
            version = ensure_profile_version(profile)
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT platform, title FROM scraped_jobs WHERE id = ?", (req.job_id,))
                job = cursor.fetchone()
                if job:
                    cursor.execute("""INSERT INTO application_attribution(job_id, profile_version, target_role, platform)
                        VALUES (?, ?, ?, ?) ON CONFLICT(job_id) DO NOTHING""",
                        (req.job_id, version, profile.get("target_role") or job["title"], job["platform"]))
                    conn.commit()
            finally:
                conn.close()
        return result
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class ConfirmSubmissionRequest(BaseModel):
    job_id: str
    execution_mode: str = "live"
    message: str = "Portal başvurusu kullanıcı/portal doğrulamasıyla onaylandı."


@router.post("/outcome/confirm_submission")
def confirm_submission(req: ConfirmSubmissionRequest):
    try:
        conn = get_db_connection()
        try:
            previous = conn.cursor().execute("SELECT status FROM scraped_jobs WHERE id = ?", (req.job_id,)).fetchone()
        finally:
            conn.close()
        result = kanban_manager.confirm_submission(req.job_id, req.execution_mode, req.message)
        record_status_transition(
            req.job_id,
            previous["status"] if previous else None,
            "Applied",
            source="submission_confirmation",
            note=req.message,
        )
        return result
    except ValueError as exc:
        status_code = 404 if str(exc) == "Job not found" else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/outcome/analytics")
def get_analytics():
    return calculate_funnel_metrics()


@router.get("/outcome/interview-responses")
def get_interview_responses():
    """List only externally confirmed applications that reached interview/offer."""
    conn = get_db_connection()
    try:
        rows = conn.cursor().execute("""
            SELECT id, title, company, platform, url, status, applied_at
            FROM scraped_jobs
            WHERE submission_confirmed = 1 AND status IN ('Interview', 'Offer')
            ORDER BY COALESCE(applied_at, created_at) DESC
        """).fetchall()
        return {"responses": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.get("/outcome/status-history/{job_id}")
def get_status_history(job_id: str):
    return {"history": list_status_history(job_id)}


@router.get("/outcome/today")
def get_today():
    return get_today_actions()


@router.get("/outcome/follow_ups")
def get_follow_ups():
    return {"follow_ups": get_pending_follow_ups()}
