"""Ranking, salary intelligence, learning, reporting, and Notion endpoints."""

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator
from urllib.parse import urlparse

from backend.app.api.profile import fetch_candidate_profile
from backend.app.modules.outcome.html_report import html_report_generator
from backend.app.modules.outcome.notion_sync import notion_sync
from backend.app.modules.rank.rank_state import rank_state_manager
from backend.app.modules.rank.salary_lookup import salary_lookup
from backend.app.modules.scrape.seen_jobs_tracker import seen_jobs_tracker
from backend.app.modules.upskill import upskill_engine


router = APIRouter()


class RankCandidatesRequest(BaseModel):
    focus: Optional[str] = None
    limit: int = 50
    include_all: bool = False


@router.post("/rank/candidates")
@router.post("/api/rank/candidates")
def get_rank_candidates(req: RankCandidatesRequest):
    return rank_state_manager.get_candidates(req.focus, req.limit, req.include_all)


class ApplyScoresRequest(BaseModel):
    results: List[Dict[str, Any]]
    dry_run: bool = False


@router.post("/rank/apply_scores")
@router.post("/api/rank/apply_scores")
def apply_rank_scores(req: ApplyScoresRequest):
    return rank_state_manager.apply_scores(req.results, req.dry_run)


class SweepRequest(BaseModel):
    dry_run: bool = True
    exclude_keys: Optional[List[str]] = None


@router.post("/rank/sweep")
@router.post("/api/rank/sweep")
def rank_sweep(req: SweepRequest):
    return rank_state_manager.sweep_and_report(req.dry_run, req.exclude_keys)


@router.get("/rank/summary")
@router.get("/api/rank/summary")
def get_ranking_summary():
    return rank_state_manager.get_ranking_summary()


class SalarySearchRequest(BaseModel):
    query: str
    city: Optional[str] = None


@router.post("/rank/salary/search")
@router.post("/api/rank/salary/search")
def search_salary(req: SalarySearchRequest):
    results = salary_lookup.search(req.query, req.city)
    return {"results": results, "count": len(results)}


class SalaryAddRequest(BaseModel):
    company: str
    city: Optional[str] = ""
    salary_min: Optional[float] = None
    salary_median: Optional[float] = None
    salary_max: Optional[float] = None
    currency: str = "USD"
    period: str = "year"
    notes: str = ""
    source_type: Literal["user_reported", "company_disclosed", "survey", "job_posting", "other"] = "user_reported"
    source_name: str = Field(default="", max_length=300)
    source_url: str = Field(default="", max_length=2000)
    as_of: str = Field(default="", max_length=10)
    sample_size: Optional[int] = Field(default=None, ge=1, le=1_000_000)
    source_count: Optional[int] = Field(default=None, ge=1, le=10_000)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        value = value.strip()
        if value:
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Source URL must use http or https.")
        return value

    @field_validator("as_of")
    @classmethod
    def validate_as_of(cls, value: str) -> str:
        value = value.strip()
        if value:
            from datetime import date
            date.fromisoformat(value)
        return value


@router.post("/rank/salary/add")
@router.post("/api/rank/salary/add")
def add_salary_entry(req: SalaryAddRequest):
    return salary_lookup.add_company(
        req.company,
        req.city or "",
        req.salary_min,
        req.salary_median,
        req.salary_max,
        req.currency,
        req.period,
        notes=req.notes,
        source_type=req.source_type,
        source_name=req.source_name,
        source_url=req.source_url,
        as_of=req.as_of,
        sample_size=req.sample_size,
        source_count=req.source_count,
    )


class SalaryImportRequest(BaseModel):
    entries: List[Dict[str, Any]]


@router.post("/rank/salary/import")
@router.post("/api/rank/salary/import")
def import_salary_data(req: SalaryImportRequest):
    return salary_lookup.import_from_list(req.entries)


@router.get("/rank/salary/validate")
@router.get("/api/rank/salary/validate")
def validate_salary_data():
    return salary_lookup.validate()


@router.get("/rank/salary/stats")
@router.get("/api/rank/salary/stats")
def salary_stats():
    return salary_lookup.stats()


class UpskillPathRequest(BaseModel):
    missing_skills: List[str] = Field(min_length=1, max_length=30)
    candidate_skills: Optional[List[str]] = None
    max_hours_per_week: int = Field(default=10, ge=1, le=40)


@router.post("/upskill/generate_path")
@router.post("/api/upskill/generate_path")
def generate_learning_path(req: UpskillPathRequest):
    candidate_skills = req.candidate_skills
    if not candidate_skills:
        candidate_skills = fetch_candidate_profile().get("skills", [])
    return upskill_engine.generate_learning_path(
        req.missing_skills, candidate_skills, req.max_hours_per_week
    )


class UpskillProgressRequest(BaseModel):
    skill: str = Field(min_length=1, max_length=200)
    status: Literal["not_started", "in_progress", "completed", "skipped"]
    notes: Optional[str] = ""


@router.post("/upskill/progress")
@router.post("/api/upskill/progress")
def update_upskill_progress(req: UpskillProgressRequest):
    return upskill_engine.mark_progress(req.skill, req.status, req.notes or "")


@router.get("/upskill/progress")
@router.get("/api/upskill/progress")
def get_upskill_progress():
    return upskill_engine.get_progress()


@router.get("/upskill/plan")
def get_saved_learning_plan():
    return {"plan": upskill_engine.get_saved_plan()}


@router.post("/reports/job_search")
@router.post("/api/reports/job_search")
def generate_job_search_report():
    all_jobs = seen_jobs_tracker.get_all()
    return html_report_generator.generate_job_search_report(
        list(all_jobs.values()), seen_jobs_tracker.stats()
    )


@router.post("/reports/pipeline")
@router.post("/api/reports/pipeline")
def generate_pipeline_report():
    all_jobs = seen_jobs_tracker.get_all()
    applied = [
        value
        for value in all_jobs.values()
        if value.get("status") in ("applied", "interview", "hired", "rejected", "no_response")
    ]
    return html_report_generator.generate_pipeline_report(applied)


@router.get("/notion/status")
@router.get("/api/notion/status")
def get_notion_status():
    return notion_sync.get_status()


class NotionSyncJobRequest(BaseModel):
    job_data: Dict[str, Any]
    notion_page_id: Optional[str] = None


@router.post("/notion/sync_job")
@router.post("/api/notion/sync_job")
def sync_job_to_notion(req: NotionSyncJobRequest):
    return notion_sync.sync_job(req.job_data, req.notion_page_id)


class NotionSyncBatchRequest(BaseModel):
    jobs: List[Dict[str, Any]]


@router.post("/notion/sync_batch")
@router.post("/api/notion/sync_batch")
def sync_batch_to_notion(req: NotionSyncBatchRequest):
    return notion_sync.sync_batch(req.jobs)
