"""Real-time orchestration, follow-up and outreach endpoints."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.app.api.profile import fetch_candidate_profile
from backend.app.core.database import get_db_connection
from backend.app.core.ws_manager import ws_manager
from backend.app.modules.outcome.follow_up_cadence import follow_up_cadence_engine


router = APIRouter()


@router.websocket("/ws/events")
async def websocket_event_channel(websocket: WebSocket, api_key: Optional[str] = Query(default=None)):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)


class OptimizeLinkedInRequest(BaseModel):
    target_role: Optional[str] = None


class AuditGitHubRequest(BaseModel):
    github_username: str
    sample_projects: Optional[List[Dict[str, Any]]] = None


class GenerateCadenceRequest(BaseModel):
    company: str
    title: str
    recruiter_name: Optional[str] = None


@router.post("/outcome/follow_up/generate")
@router.post("/api/outcome/follow_up/generate")
def generate_follow_up_cadence(req: GenerateCadenceRequest):
    return follow_up_cadence_engine.generate_cadence_messages(
        req.company, req.title, req.recruiter_name
    )


@router.get("/outcome/follow_up/pending")
@router.get("/api/outcome/follow_up/pending")
def get_pending_follow_ups():
    return {"pending_follow_ups": follow_up_cadence_engine.get_pending_follow_ups()}


@router.post("/outcome/follow_up/{job_id}/resolve")
@router.post("/api/outcome/follow_up/{job_id}/resolve")
def resolve_follow_up_reminders(job_id: str):
    """Dismiss pending reminder drafts after the user has handled them."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE follow_up_queue SET status = 'CANCELLED' WHERE job_id = ? AND status = 'PENDING'",
            (job_id,),
        )
        resolved = max(0, cursor.rowcount)
        cursor.execute(
            "UPDATE user_notifications SET read_at = CURRENT_TIMESTAMP WHERE href = ? AND read_at IS NULL",
            (f"/follow-up?job_id={job_id}",),
        )
        conn.commit()
        return {"status": "SUCCESS", "resolved_count": resolved}
    finally:
        conn.close()


class CalendarEventRequest(BaseModel):
    title: str
    company: str
    interview_time_iso: str
    duration_minutes: Optional[int] = 45
    meeting_link: Optional[str] = ""


@router.post("/outcome/calendar/event_url")
@router.post("/api/outcome/calendar/event_url")
def create_google_calendar_url(req: CalendarEventRequest):
    url = follow_up_cadence_engine.generate_google_calendar_url(
        title=req.title,
        company=req.company,
        interview_time_iso=req.interview_time_iso,
        duration_minutes=req.duration_minutes or 45,
        meeting_link=req.meeting_link or "",
    )
    return {"calendar_url": url}


class GenerateOutreachRequest(BaseModel):
    manager_name: str
    manager_title: str
    company: str
    target_role: str
    recent_news_or_stack: Optional[str] = None


class OutreachStatusRequest(BaseModel):
    outreach_id: str
    status: str

