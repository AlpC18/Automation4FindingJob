"""Inbox automation, OAuth mail connections, and distributed task API."""

from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from backend.app.core.event_logger import agent_logger
from backend.app.core.config import settings
from backend.app.core.auth_sessions import issue_oauth_state, verify_token
from backend.app.core.tenant import get_tenant_id, reset_tenant_id, set_tenant_id
from backend.app.modules.outcome.inbox_agent import inbox_agent
from backend.app.modules.outcome.oauth_mail_agent import oauth_mail_agent
from backend.app.tasks.dispatcher import task_dispatcher
from backend.app.tasks.job_store import get_job, list_jobs, serialize_job

router = APIRouter()


@router.get("/inbox/messages")
def get_inbox_messages():
    return {"messages": inbox_agent.get_all_messages()}


class SimulateEmailRequest(BaseModel):
    sender_email: str
    sender_name: str
    subject: str
    body_text: str
    job_id: Optional[str] = None


@router.post("/inbox/simulate_email")
async def simulate_incoming_email(req: SimulateEmailRequest):
    agent_logger.log_event("INBOX_AGENT", f"Processing incoming email from {req.sender_name} <{req.sender_email}>...")
    return await inbox_agent.ingest_incoming_email(
        sender_email=req.sender_email,
        sender_name=req.sender_name,
        subject=req.subject,
        body_text=req.body_text,
        job_id=req.job_id,
    )


class ApproveReplyRequest(BaseModel):
    message_id: int
    final_reply: str


@router.post("/inbox/send_reply")
def send_inbox_reply(req: ApproveReplyRequest):
    return inbox_agent.approve_and_send_reply(req.message_id, req.final_reply)


class UpdateMessageStatusRequest(BaseModel):
    status: str


@router.patch("/inbox/messages/{message_id}")
@router.patch("/api/inbox/messages/{message_id}")
def update_inbox_message(message_id: int, req: UpdateMessageStatusRequest):
    ok = inbox_agent.update_message_status(message_id, req.status)
    if not ok:
        raise HTTPException(status_code=404, detail="Message not found.")
    return {"updated": True, "message_id": message_id, "status": req.status}


@router.delete("/inbox/messages/{message_id}")
@router.delete("/api/inbox/messages/{message_id}")
def delete_inbox_message(message_id: int):
    ok = inbox_agent.delete_message(message_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Message not found.")
    return {"deleted": True, "message_id": message_id}


@router.get("/tasks/status")
@router.get("/api/tasks/status")
def get_task_queue_status():
    return task_dispatcher.get_queue_status()


class DispatchScrapeRequest(BaseModel):
    keywords: str
    location: str
    limit: Optional[int] = 15
    queries: Optional[list[str]] = None
    platforms: Optional[list[str]] = None
    remote_type: Optional[str] = None
    replace_current_feed: bool = True


@router.post("/tasks/dispatch_scrape")
@router.post("/api/tasks/dispatch_scrape")
async def dispatch_scrape_queue(req: DispatchScrapeRequest, idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    return await task_dispatcher.dispatch_scrape(
        req.keywords,
        req.location,
        req.limit or 15,
        tenant_id=get_tenant_id(),
        idempotency_key=idempotency_key,
        scrape_options={
            "queries": req.queries,
            "platforms": req.platforms,
            "location_preference": req.location,
            "remote_type": req.remote_type,
            "replace_current_feed": req.replace_current_feed,
        },
    )


@router.get("/tasks/jobs")
@router.get("/api/tasks/jobs")
def get_background_jobs(limit: int = 50):
    return {"jobs": [serialize_job(row) for row in list_jobs(max(1, min(limit, 200)))]}


@router.get("/tasks/jobs/{job_id}")
@router.get("/api/tasks/jobs/{job_id}")
def get_background_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Background job not found.")
    return {"job": serialize_job(job)}


@router.post("/tasks/jobs/{job_id}/retry")
@router.post("/api/tasks/jobs/{job_id}/retry")
async def retry_background_job(job_id: str):
    try:
        return await task_dispatcher.retry_scrape(job_id, tenant_id=get_tenant_id())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/inbox/oauth/status")
@router.get("/api/inbox/oauth/status")
def get_oauth_status():
    return oauth_mail_agent.get_accounts_status()


@router.get("/inbox/oauth/google/auth_url")
@router.get("/api/inbox/oauth/google/auth_url")
def get_google_oauth_url():
    try:
        auth_url = oauth_mail_agent.get_google_auth_url()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if settings.MULTI_TENANT_ENABLED:
        parsed = urlsplit(auth_url)
        query = parse_qsl(parsed.query)
        query.append(("state", issue_oauth_state(get_tenant_id() or "")))
        auth_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
    return {"auth_url": auth_url}


@router.get("/inbox/oauth/google/callback")
@router.get("/api/inbox/oauth/google/callback")
async def handle_google_oauth_callback(code: str, state: Optional[str] = None):
    tenant_token = None
    if settings.MULTI_TENANT_ENABLED:
        try:
            claims = verify_token(state or "", "oauth_state")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid OAuth state.") from exc
        tenant_token = set_tenant_id(claims["sub"])
    try:
        await oauth_mail_agent.handle_google_callback(code)
    finally:
        if tenant_token:
            reset_tenant_id(tenant_token)
    return RedirectResponse(url=f"{settings.FRONTEND_PUBLIC_URL}/inbox?oauth=google_success")


class ConnectMockOAuthRequest(BaseModel):
    provider: str


@router.post("/inbox/oauth/connect_instant")
@router.post("/api/inbox/oauth/connect_instant")
async def connect_oauth_instant(req: ConnectMockOAuthRequest):
    if not settings.DEMO_DATA_ENABLED:
        raise HTTPException(status_code=404, detail="Simülasyon OAuth akışı kapalı. Gerçek sağlayıcı OAuth bağlantısını kullanın.")
    if req.provider == "google":
        return await oauth_mail_agent.handle_google_callback("mock_auth_code_123")
    return await oauth_mail_agent.handle_microsoft_callback("mock_auth_code_456")


@router.get("/inbox/oauth/microsoft/auth_url")
@router.get("/api/inbox/oauth/microsoft/auth_url")
def get_microsoft_oauth_url():
    try:
        auth_url = oauth_mail_agent.get_microsoft_auth_url()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if settings.MULTI_TENANT_ENABLED:
        parsed = urlsplit(auth_url)
        query = parse_qsl(parsed.query)
        query.append(("state", issue_oauth_state(get_tenant_id() or "")))
        auth_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
    return {"auth_url": auth_url}


@router.get("/inbox/oauth/microsoft/callback")
@router.get("/api/inbox/oauth/microsoft/callback")
async def handle_microsoft_oauth_callback(code: str, state: Optional[str] = None):
    tenant_token = None
    if settings.MULTI_TENANT_ENABLED:
        try:
            claims = verify_token(state or "", "oauth_state")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid OAuth state.") from exc
        tenant_token = set_tenant_id(claims["sub"])
    try:
        await oauth_mail_agent.handle_microsoft_callback(code)
    finally:
        if tenant_token:
            reset_tenant_id(tenant_token)
    return RedirectResponse(url=f"{settings.FRONTEND_PUBLIC_URL}/inbox?oauth=ms_success")


class DisconnectOAuthRequest(BaseModel):
    provider: str


@router.post("/inbox/oauth/disconnect")
@router.post("/api/inbox/oauth/disconnect")
def disconnect_oauth_account(req: DisconnectOAuthRequest):
    return oauth_mail_agent.disconnect(req.provider)


class SyncOAuthEmailsRequest(BaseModel):
    provider: Optional[str] = None


@router.post("/inbox/oauth/sync")
@router.post("/api/inbox/oauth/sync")
async def sync_oauth_inbox(req: Optional[SyncOAuthEmailsRequest] = None):
    return await oauth_mail_agent.sync_emails(req.provider if req else None)
