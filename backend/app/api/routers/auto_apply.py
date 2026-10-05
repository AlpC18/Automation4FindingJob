"""Auto-apply domain API."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.modules.apply.auto_apply_pipeline import auto_apply_pipeline

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
    return {
        "queue": auto_apply_pipeline.list_queue(status_filter=status),
        "today_applied_count": auto_apply_pipeline.get_today_count(),
    }


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
