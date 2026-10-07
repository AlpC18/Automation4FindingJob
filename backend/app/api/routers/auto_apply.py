"""Auto-apply domain API."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.api.profile import fetch_candidate_profile
from backend.app.modules.apply.auto_apply_pipeline import auto_apply_pipeline
from backend.app.modules.apply.claim_check import find_unsupported_claims
from backend.app.modules.setup.rag_engine import rag_memory

router = APIRouter()


class AutoApplyScanRequest(BaseModel):
    min_score: int = 75
    max_daily_limit: int = 5
    auto_request_approval: bool = True


@router.post("/apply/auto/scan")
@router.post("/api/apply/auto/scan")
async def scan_and_prepare_auto_apply(req: AutoApplyScanRequest):
    return await auto_apply_pipeline.scan_and_prepare(
        min_score=req.min_score,
        max_daily_limit=req.max_daily_limit,
        auto_request_approval=req.auto_request_approval,
    )


@router.get("/apply/auto/queue")
@router.get("/api/apply/auto/queue")
def list_auto_apply_queue(status: Optional[str] = None):
    # Flags are worked out on every read, so they follow the current CV and saved projects
    # (a project added after the draft was written can clear a flag).
    profile = fetch_candidate_profile()
    queue = []
    for item in auto_apply_pipeline.list_queue(status_filter=status):
        draft = item.get("draft_result") or {}
        claims = find_unsupported_claims(draft.get("cover_letter") or "", profile, rag_memory.documents, item)
        queue.append({**item, "draft_result": {**draft, "unsupported_claims": claims}})
    return {"queue": queue, "today_applied_count": auto_apply_pipeline.get_today_count()}


class AutoApplyActionRequest(BaseModel):
    job_key: str
    reason: Optional[str] = ""
    headless: Optional[bool] = True


@router.post("/apply/auto/approve")
@router.post("/api/apply/auto/approve")
async def approve_auto_apply(req: AutoApplyActionRequest):
    return await auto_apply_pipeline.approve_application(req.job_key)


@router.post("/apply/auto/submit")
@router.post("/api/apply/auto/submit")
async def submit_approved_auto_apply(req: AutoApplyActionRequest):
    return await auto_apply_pipeline.submit_approved_application(req.job_key, req.headless is not False)


@router.post("/apply/auto/confirm-submission")
@router.post("/api/apply/auto/confirm-submission")
def confirm_manual_auto_apply(req: AutoApplyActionRequest):
    return auto_apply_pipeline.confirm_manual_submission(req.job_key)


@router.post("/apply/auto/reject")
@router.post("/api/apply/auto/reject")
def reject_auto_apply(req: AutoApplyActionRequest):
    return auto_apply_pipeline.reject_application(req.job_key, req.reason or "")
