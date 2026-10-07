"""Salary records the user saves, and HTML reports of the job search."""

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator
from urllib.parse import urlparse

from backend.app.modules.outcome.html_report import html_report_generator
from backend.app.modules.rank.salary_lookup import salary_lookup
from backend.app.modules.scrape.job_feed import feed_jobs


router = APIRouter()


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


@router.post("/reports/job_search")
@router.post("/api/reports/job_search")
def generate_job_search_report():
    return html_report_generator.generate_job_search_report(list(feed_jobs().values()), {})


@router.post("/reports/pipeline")
@router.post("/api/reports/pipeline")
def generate_pipeline_report():
    all_jobs = feed_jobs()
    applied = [
        value
        for value in all_jobs.values()
        if value.get("status") in ("applied", "interview", "hired", "rejected", "no_response")
    ]
    return html_report_generator.generate_pipeline_report(applied)
