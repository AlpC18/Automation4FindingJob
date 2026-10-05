"""Job sourcing, browser inspection, and extension copilot API."""

import asyncio
import json
import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from backend.app.api.profile import fetch_candidate_profile
from backend.app.core.config import settings
from backend.app.core.database import get_db_connection
from backend.app.core.event_logger import agent_logger
from backend.app.core.tenant import get_tenant_id
from backend.app.modules.rank.scoring_engine import rank_and_save_all_jobs, score_job_against_profile
from backend.app.modules.rank.llm_reranker import review_top_jobs
from backend.app.modules.scrape.rate_limiter import account_health
from backend.app.modules.scrape.session_manager import linkedin_session_manager
from backend.app.modules.scrape.stealth_browser import stealth_worker
from backend.app.modules.scrape.unified_scraper import unified_scraper
from backend.app.modules.scrape.saved_search_service import run_saved_search as execute_saved_search
from backend.app.modules.scrape.live_sources import apify_job_source, company_board_job_sources
from backend.app.modules.scrape.public_feeds import COMPANY_BOARD_PROVIDERS, parse_board_reference
from backend.app.modules.scrape.apify_budget import get_apify_quota_summary, list_quota_snapshots, record_quota_snapshot
from backend.app.modules.outcome.job_workspace import get_job_flags, get_job_flags_for_ids, set_job_flag
from backend.app.modules.scrape.job_link_health import check_job_link, get_job_link_check, get_job_link_checks
from backend.app.tasks.dispatcher import task_dispatcher
from backend.app.modules.scrape.scan_status import get_scan_status
from backend.app.modules.scrape.source_registry import (
    ACTOR_SOURCES,
    get_source_config,
    delete_company_board,
    get_source_health,
    list_company_boards,
    list_scan_runs,
    save_company_board,
    public_source_config,
    save_source_config,
)

router = APIRouter()


class ScrapeRequest(BaseModel):
    query: Optional[str] = None
    queries: Optional[List[str]] = None
    location_preference: Optional[str] = None
    remote_type: Optional[str] = None
    platforms: Optional[List[str]] = None
    # A manual scan represents the current search snapshot. Historical
    # applications are preserved, while old unprocessed listings are replaced
    # only for sources that completed successfully.
    replace_current_feed: bool = True


class SourceConfigRequest(BaseModel):
    actor_id: str = ""
    api_token: Optional[str] = None
    input_json: str = "{}"
    enabled: bool = True


class SavedSearchRequest(BaseModel):
    name: str
    queries: List[str]
    location: Optional[str] = ""
    min_match_score: float = 0
    # Saving a search never schedules it implicitly; automation is opt-in.
    enabled: bool = False


class SavedSearchScheduleRequest(BaseModel):
    enabled: bool


@router.get("/scrape/saved-searches")
def list_saved_searches():
    conn = get_db_connection()
    try:
        rows = conn.cursor()
        rows.execute("SELECT * FROM saved_searches ORDER BY created_at DESC")
        return {"searches": [{**dict(row), "queries": json.loads(row["queries_json"])} for row in rows.fetchall()]}
    finally:
        conn.close()


@router.post("/scrape/saved-searches")
def create_saved_search(req: SavedSearchRequest):
    queries = list(dict.fromkeys(query.strip() for query in req.queries if query.strip()))
    if not queries or not req.name.strip():
        raise HTTPException(status_code=422, detail="Arama adı ve en az bir rol gerekli.")
    search_id = uuid.uuid4().hex
    conn = get_db_connection()
    try:
        conn.cursor().execute("INSERT INTO saved_searches(id, name, queries_json, location, min_match_score, enabled) VALUES (?, ?, ?, ?, ?, ?)",
                              (search_id, req.name.strip(), json.dumps(queries), req.location or "", max(0, min(100, req.min_match_score)), int(req.enabled)))
        conn.commit()
    finally:
        conn.close()
    return {"id": search_id, "name": req.name.strip(), "queries": queries, "location": req.location or "", "min_match_score": req.min_match_score, "enabled": req.enabled}


@router.delete("/scrape/saved-searches/{search_id}")
def delete_saved_search(search_id: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM saved_searches WHERE id = ?", (search_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Saved search not found.")
        cursor.execute("DELETE FROM saved_searches WHERE id = ?", (search_id,))
        conn.commit()
    finally:
        conn.close()
    return {"deleted": True}


@router.patch("/scrape/saved-searches/{search_id}")
def update_saved_search_schedule(search_id: str, req: SavedSearchScheduleRequest):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM saved_searches WHERE id = ?", (search_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Saved search not found.")
        cursor.execute("UPDATE saved_searches SET enabled = ? WHERE id = ?", (int(req.enabled), search_id))
        conn.commit()
        return {"id": search_id, "enabled": req.enabled}
    finally:
        conn.close()


@router.post("/scrape/saved-searches/{search_id}/run")
def run_saved_search(search_id: str):
    try:
        return execute_saved_search(search_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/notifications")
def list_notifications():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_notifications ORDER BY created_at DESC LIMIT 50")
        return {"notifications": [dict(row) for row in cursor.fetchall()]}
    finally:
        conn.close()


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str):
    conn = get_db_connection()
    try:
        conn.cursor().execute("UPDATE user_notifications SET read_at = CURRENT_TIMESTAMP WHERE id = ?", (notification_id,))
        conn.commit()
        return {"read": True}
    finally:
        conn.close()


class CompanyBoardRequest(BaseModel):
    board: str = Field(min_length=3, max_length=300)


@router.get("/scrape/company-boards")
def get_company_boards():
    return {"boards": list_company_boards(), "providers": list(COMPANY_BOARD_PROVIDERS)}


@router.post("/scrape/company-boards")
def add_company_board(req: CompanyBoardRequest):
    try:
        provider, slug = parse_board_reference(req.board)
        open_jobs = company_board_job_sources.verify(provider, slug)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    save_company_board(provider, slug)
    return {"board": {"provider": provider, "slug": slug, "origin": "saved"}, "open_jobs": open_jobs, "boards": list_company_boards()}


@router.delete("/scrape/company-boards/{provider}/{slug}")
def remove_company_board(provider: str, slug: str):
    delete_company_board(provider.lower(), slug.lower())
    return {"boards": list_company_boards()}


@router.get("/scrape/sources")
def get_sources():
    return {"sources": [public_source_config(source) for source in ACTOR_SOURCES], "health": get_source_health()}


@router.get("/scrape/apify-quota")
def get_apify_quota(force_refresh: bool = False):
    summary = get_apify_quota_summary("linkedin", force_refresh=force_refresh)
    record_quota_snapshot(summary)
    return summary


@router.get("/scrape/apify-quota/history")
def get_apify_quota_history(limit: int = Query(default=24, ge=1, le=100)):
    return {"snapshots": list_quota_snapshots(limit)}


@router.post("/scrape/sources/{source}/tokens/reveal")
def reveal_source_tokens(source: str, request: Request, response: Response):
    """Explicitly reveal saved keys only in a local development session."""
    if source not in ACTOR_SOURCES:
        raise HTTPException(status_code=404, detail="Unknown job source.")
    client_host = request.client.host if request.client else ""
    if settings.ENVIRONMENT.lower() == "production" or client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise HTTPException(status_code=403, detail="Secret reveal is available only from this local development app.")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    config = get_source_config(source)
    return {"tokens": config.get("api_tokens", [])}


@router.put("/scrape/sources/{source}")
def update_source(source: str, req: SourceConfigRequest):
    if source not in ACTOR_SOURCES:
        raise HTTPException(status_code=404, detail="Unknown job source.")
    if req.api_token and settings.ENVIRONMENT == "production" and not settings.APP_ENCRYPTION_KEY:
        raise HTTPException(status_code=503, detail="Configure APP_ENCRYPTION_KEY before saving provider credentials.")
    try:
        save_source_config(source, actor_id=req.actor_id, api_token=req.api_token, input_json=req.input_json, enabled=req.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"source": public_source_config(source), "health": get_source_health()[source]}


@router.post("/scrape/sources/{source}/test")
def test_source_connection(source: str, req: SourceConfigRequest):
    if source not in ACTOR_SOURCES:
        raise HTTPException(status_code=404, detail="Unknown job source.")
    try:
        return apify_job_source.test_connection(
            source, actor_id_override=req.actor_id, api_token_override=req.api_token,
            input_json_override=req.input_json,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/scrape/run")
@router.post("/api/scrape/run")
async def trigger_scrape(req: ScrapeRequest, idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    query = req.query or settings.DEFAULT_SCRAPE_QUERY
    return await task_dispatcher.dispatch_scrape(
        keywords=query,
        location=req.location_preference or "",
        tenant_id=get_tenant_id(),
        idempotency_key=idempotency_key,
        scrape_options={
            "platforms": req.platforms,
            "queries": req.queries,
            "location_preference": req.location_preference,
            "remote_type": req.remote_type,
            "replace_current_feed": req.replace_current_feed,
        },
    )


def _serialize_job(row) -> dict:
    job = dict(row)
    job["ghost_reasons"] = json.loads(job.get("ghost_reasons") or "[]")
    job["red_flags"] = json.loads(job.get("red_flags") or "[]")
    job["skill_gaps"] = json.loads(job.get("skill_gaps") or "{}")
    job["salary_benchmark"] = json.loads(job.get("salary_benchmark_json") or "{}")
    job["source_aliases"] = json.loads(job.get("source_aliases_json") or "[]")
    job["ai_review"] = json.loads(job.pop("ai_review_json", None) or "null")
    return job


@router.get("/scrape/jobs")
def get_all_jobs(
    q: Optional[str] = Query(default=None, max_length=200),
    platform: Optional[str] = Query(default=None, max_length=50),
    location: Optional[str] = Query(default=None, max_length=100),
    remote_type: Optional[str] = Query(default=None, max_length=50),
    min_match_score: float = Query(default=0, ge=0, le=100),
    status: Optional[str] = Query(default=None, max_length=40),
    include_history: bool = True,
    include_stale: bool = False,
    include_hidden: bool = False,
    flag: Optional[Literal["favorite", "hidden"]] = None,
    sort: str = Query(default="match", pattern="^(match|recent|company)$"),
):
    conn = get_db_connection()
    cursor = conn.cursor()
    clauses = ["1 = 1"]
    params: list[Any] = []
    if not include_stale:
        clauses.append("stale_at IS NULL")
    if not include_hidden:
        clauses.append("NOT EXISTS (SELECT 1 FROM job_flags hidden_flags WHERE hidden_flags.job_id = scraped_jobs.id AND hidden_flags.hidden = 1)")
    if flag == "favorite":
        clauses.append("EXISTS (SELECT 1 FROM job_flags favorite_flags WHERE favorite_flags.job_id = scraped_jobs.id AND favorite_flags.favorite = 1)")
    elif flag == "hidden":
        clauses.append("EXISTS (SELECT 1 FROM job_flags hidden_flags WHERE hidden_flags.job_id = scraped_jobs.id AND hidden_flags.hidden = 1)")
    if q and q.strip():
        clauses.append("(lower(title) LIKE ? OR lower(company) LIKE ? OR lower(description) LIKE ?)")
        term = f"%{q.strip().lower()}%"
        params.extend([term, term, term])
    if platform and platform.lower() != "all":
        clauses.append("lower(platform) = ?")
        params.append(platform.lower())
    if location and location.strip():
        clauses.append("lower(location) LIKE ?")
        params.append(f"%{location.strip().lower()}%")
    if remote_type and remote_type.lower() != "all":
        clauses.append("lower(remote_type) LIKE ?")
        params.append(f"%{remote_type.strip().lower()}%")
    if min_match_score:
        clauses.append("COALESCE(match_score, 0) >= ?")
        params.append(min_match_score)
    if status and status.lower() != "all":
        clauses.append("status = ?")
        params.append(status)
    elif not include_history:
        clauses.append("COALESCE(status, 'Draft') IN ('Draft', 'New', '')")
    ordering = {
        "match": "COALESCE(match_score, 0) DESC, created_at DESC",
        "recent": "created_at DESC",
        "company": "lower(company) ASC, lower(title) ASC",
    }[sort]
    cursor.execute(f"SELECT * FROM scraped_jobs WHERE {' AND '.join(clauses)} ORDER BY {ordering}", params)
    rows = cursor.fetchall()
    conn.close()
    jobs = [_serialize_job(row) for row in rows]
    flags = get_job_flags_for_ids([job["id"] for job in jobs])
    link_checks = get_job_link_checks([job["id"] for job in jobs])
    for job in jobs:
        item = flags.get(job["id"], {})
        job["favorite"] = bool(item.get("favorite", False))
        job["hidden"] = bool(item.get("hidden", False))
        job["flag_note"] = item.get("note", "")
        job["source_link_check"] = link_checks.get(job["id"])
    current_feed_jobs = [job for job in jobs if (job.get("status") or "Draft") in {"Draft", "New", ""}]
    return {"jobs": jobs, "total": len(jobs), "current_feed_total": len(current_feed_jobs)}


class JobFlagRequest(BaseModel):
    flag: Literal["favorite", "hidden"]
    enabled: bool
    note: str = ""


@router.get("/scrape/jobs/{job_id}/flags")
def get_job_flags_endpoint(job_id: str):
    return get_job_flags(job_id)


@router.post("/scrape/jobs/{job_id}/flags")
def set_job_flags_endpoint(job_id: str, req: JobFlagRequest):
    try:
        return set_job_flag(job_id, req.flag, req.enabled, req.note)
    except ValueError as exc:
        raise HTTPException(status_code=404 if str(exc) == "Job not found" else 422, detail=str(exc)) from exc


@router.get("/scrape/jobs/{job_id}/link-check")
def get_job_link_check_endpoint(job_id: str):
    return {"check": get_job_link_check(job_id)}


@router.post("/scrape/jobs/{job_id}/link-check")
def run_job_link_check_endpoint(job_id: str):
    try:
        return {"check": check_job_link(job_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/scrape/jobs/{job_id}")
def get_job_detail(job_id: str):
    conn = get_db_connection()
    try:
        row = conn.cursor().execute("SELECT * FROM scraped_jobs WHERE id = ?", (job_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found.")
    job = _serialize_job(row)
    flags = get_job_flags(job_id)
    job["favorite"] = flags["favorite"]
    job["hidden"] = flags["hidden"]
    job["flag_note"] = flags.get("note", "")
    job["source_link_check"] = get_job_link_check(job_id)
    return {"job": job}


@router.get("/scrape/runs")
def get_scan_runs(limit: int = Query(default=20, ge=1, le=100)):
    return {"runs": list_scan_runs(limit)}


@router.get("/scrape/status")
def get_scrape_status():
    """Last scan, per-source key/quota state, scheduler state and empty-feed diagnosis."""
    return get_scan_status()


@router.get("/scrape/health")
def get_account_health():
    return account_health.get_all_platform_health()


@router.post("/rank/evaluate_all")
async def rank_jobs(ai: bool = True):
    """Rule-rank every job, then let the AI provider re-read the best ones (``ai=false`` skips that)."""
    profile = fetch_candidate_profile()
    ranked = await asyncio.to_thread(rank_and_save_all_jobs, profile)
    ai_review = await review_top_jobs(profile) if ai else {"status": "skipped", "reason": "not_requested"}
    return {"status": "SUCCESS", "total_ranked": len(ranked), "ai_review": ai_review}


class PlaywrightApplyRequest(BaseModel):
    job_id: str
    headless: Optional[bool] = True
    submit: Optional[bool] = False


@router.post("/scrape/playwright_apply")
async def execute_playwright_apply(req: PlaywrightApplyRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scraped_jobs WHERE id = ?", (req.job_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found.")
    profile = fetch_candidate_profile()
    agent_logger.log_event("PLAYWRIGHT", f"Initiating stealth browser session for {row['title']} @ {row['company']}...")
    result = await stealth_worker.execute_easy_apply_flow(
        job_url=row["url"] or "https://www.linkedin.com/jobs",
        applicant_data=profile,
        headless=req.headless,
        submit=req.submit,
    )
    agent_logger.log_event("PLAYWRIGHT", f"Playwright session completed: {result['status']}.")
    return result


class SyncLinkedInSessionRequest(BaseModel):
    cookies: List[Dict[str, Any]]


@router.post("/scrape/sync_linkedin_session")
@router.post("/api/scrape/sync_linkedin_session")
def sync_linkedin_session(req: SyncLinkedInSessionRequest):
    return linkedin_session_manager.save_cookies(req.cookies)


@router.get("/scrape/linkedin_session_status")
@router.get("/api/scrape/linkedin_session_status")
def get_linkedin_session_status():
    return linkedin_session_manager.get_status()


@router.post("/scrape/clear_linkedin_session")
@router.post("/api/scrape/clear_linkedin_session")
def clear_linkedin_session():
    return linkedin_session_manager.clear_cookies()


class AnalyzeOnTheFlyRequest(BaseModel):
    title: str
    company: str
    description: str
    location: Optional[str] = "Remote"


@router.post("/scrape/analyze_on_the_fly")
def analyze_job_on_the_fly(req: AnalyzeOnTheFlyRequest):
    temp_job = {
        "id": "ext_copilot",
        "title": req.title,
        "company": req.company,
        "description": req.description,
        "location": req.location or "Remote",
        "posted_date": "Today",
        "remote_type": "Remote",
    }
    ranked = score_job_against_profile(temp_job, fetch_candidate_profile())
    agent_logger.log_event("EXTENSION_COPILOT", f"On-page analysis for {req.title} @ {req.company}: %{ranked.get('match_score', 0)} ATS.")
    return ranked
