"""Persistent seen-job lifecycle and ranking API."""

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.modules.scrape.seen_jobs_tracker import seen_jobs_tracker

router = APIRouter()


@router.get("/scrape/seen_jobs/stats")
def get_seen_jobs_stats():
    return seen_jobs_tracker.stats()


@router.get("/scrape/seen_jobs/new")
def get_new_seen_jobs():
    jobs = seen_jobs_tracker.get_new_jobs()
    return {"count": len(jobs), "jobs": jobs}


@router.get("/scrape/seen_jobs/ranked")
def get_ranked_seen_jobs(min_score: float = 0.0):
    jobs = seen_jobs_tracker.get_ranked_jobs(min_score)
    return {"count": len(jobs), "jobs": jobs}


@router.get("/scrape/seen_jobs/closing_soon")
def get_closing_soon_jobs(days: int = 7):
    jobs = seen_jobs_tracker.get_closing_soon(days)
    return {"count": len(jobs), "jobs": jobs, "urgency_window_days": days}


class AddSeenJobRequest(BaseModel):
    company: str
    title: str
    url: Optional[str] = ""
    portal: Optional[str] = ""
    location: Optional[str] = ""


@router.post("/scrape/seen_jobs/add")
def add_seen_job(req: AddSeenJobRequest):
    key, is_new = seen_jobs_tracker.add(
        company=req.company,
        title=req.title,
        url=req.url or "",
        portal=req.portal or "",
        location=req.location or "",
    )
    return {"key": key, "is_new": is_new}


class MarkSeenJobRequest(BaseModel):
    key: str
    status: str


@router.post("/scrape/seen_jobs/mark")
def mark_seen_job_status(req: MarkSeenJobRequest):
    success = seen_jobs_tracker.mark_status(req.key, req.status)
    return {"success": success, "key": req.key, "new_status": req.status}


class ScoreSeenJobRequest(BaseModel):
    key: str
    score: float
    strengths: Optional[List[str]] = None
    gaps: Optional[List[str]] = None
    deadline: Optional[str] = None


@router.post("/scrape/seen_jobs/score")
def score_seen_job(req: ScoreSeenJobRequest):
    success = seen_jobs_tracker.set_score(req.key, req.score, req.strengths, req.gaps, req.deadline)
    return {"success": success, "key": req.key}


@router.post("/scrape/seen_jobs/sweep_expired")
def sweep_expired_jobs(dry_run: bool = True):
    expired = seen_jobs_tracker.sweep_expired(dry_run=dry_run)
    return {"expired_count": len(expired), "dry_run": dry_run, "expired": expired}


@router.get("/scrape/seen_jobs/export")
def export_seen_jobs():
    return seen_jobs_tracker.get_all()
