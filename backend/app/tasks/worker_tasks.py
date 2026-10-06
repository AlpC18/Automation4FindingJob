"""
Celery Worker Tasks for Distributed Execution
Asynchronously handles heavy scraping, rank scoring, Playwright Easy Apply, and email sync.
"""

import asyncio
import logging
from contextlib import nullcontext
from typing import Dict, Any, List, Optional
from backend.app.tasks.celery_app import celery_app
from backend.app.core.event_logger import agent_logger
from backend.app.core.database import use_tenant
from backend.app.tasks.job_store import update_job

@celery_app.task(bind=True, name="tasks.scrape_jobs")
def task_scrape_jobs(
    self,
    keywords: str,
    location: str,
    limit: int = 15,
    tenant_id: Optional[str] = None,
    job_id: Optional[str] = None,
    query: Optional[str] = None,
    target_platforms: Optional[List[str]] = None,
    queries: Optional[List[str]] = None,
    location_preference: Optional[str] = None,
    remote_type: Optional[str] = None,
    replace_current_feed: bool = True,
) -> Dict[str, Any]:
    """Runs scraping across all job platforms asynchronously inside Celery worker."""
    from backend.app.modules.scrape.unified_scraper import unified_scraper
    agent_logger.log_event("CELERY_WORKER", f"[Task {self.request.id}] Starting background scrape for '{keywords}' in '{location}'...")
    
    with use_tenant(tenant_id) if tenant_id else nullcontext():
        if job_id:
            update_job(job_id, "running", increment_attempt=True)
        try:
            res = unified_scraper.run_multi_platform_scrape(
                query=query or keywords,
                target_platforms=target_platforms,
                queries=queries,
                location_preference=location_preference or location or None,
                remote_type=remote_type,
                replace_current_feed=replace_current_feed,
            )
            jobs = res.get("jobs", [])
            result = {
                "count": res.get("total_scraped", len(jobs)),
                "current_total": res.get("current_total", 0),
                "newly_saved_count": res.get("newly_saved_count", 0),
                "scan_id": res.get("scan_id"),
                "errors": res.get("errors", []),
            }
            if job_id:
                update_job(job_id, "succeeded", result=result)
        except Exception as exc:
            logging.getLogger("career_agent.worker").exception("Background scrape job %s failed", job_id or self.request.id)
            if job_id:
                state = "retrying" if self.request.retries < self.max_retries else "failed"
                update_job(job_id, state, error=str(exc))
            if self.request.retries < self.max_retries:
                raise self.retry(exc=exc, countdown=min(60, 2 ** (self.request.retries + 1)))
            raise
    jobs = res.get("saved_jobs", [])
    agent_logger.log_event("CELERY_WORKER", f"[Task {self.request.id}] Completed scrape. Saved {len(jobs)} jobs.")
    return {
        "status": "SUCCESS",
        "task_id": self.request.id,
        "count": len(jobs),
        "job_ids": [j.get("id") for j in jobs],
        "scan_id": res.get("scan_id"),
        "total_scraped": res.get("total_scraped", len(jobs)),
        "current_total": res.get("current_total", 0),
        "newly_saved_count": res.get("newly_saved_count", 0),
        "errors": res.get("errors", []),
    }


@celery_app.task(name="tasks.check_job_links")
def task_check_job_links(job_ids: List[str], tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Validate source links for newly discovered listings."""
    from backend.app.modules.scrape.job_link_health import _run_checks

    _run_checks(job_ids, tenant_id)
    return {"status": "SUCCESS", "checked_count": len(job_ids)}

@celery_app.task(bind=True, name="tasks.rank_all_jobs")
def task_rank_all_jobs(self) -> Dict[str, Any]:
    """Scores and ranks all unranked jobs against candidate profile."""
    from backend.app.modules.rank.scoring_engine import rank_and_save_all_jobs
    agent_logger.log_event("CELERY_WORKER", f"[Task {self.request.id}] Starting ATS evaluation of all jobs...")
    from backend.app.api.profile import fetch_candidate_profile
    results = rank_and_save_all_jobs(fetch_candidate_profile())
    agent_logger.log_event("CELERY_WORKER", f"[Task {self.request.id}] Finished ATS ranking ({len(results)} jobs processed).")
    return {
        "status": "SUCCESS",
        "task_id": self.request.id,
        "processed_count": len(results)
    }

@celery_app.task(bind=True, name="tasks.stealth_apply")
def task_stealth_apply(self, job_id: str, applicant_data: Dict[str, Any], headless: bool = True) -> Dict[str, Any]:
    """Executes Playwright stealth application in a worker process."""
    from backend.app.modules.scrape.stealth_browser import stealth_worker
    from backend.app.core.database import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scraped_jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()

    job_url = row["url"] if row and row["url"] else "https://www.linkedin.com/jobs"

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        res = loop.run_until_complete(
            stealth_worker.execute_easy_apply_flow(
                job_url=job_url,
                applicant_data=applicant_data,
                headless=headless
            )
        )
    finally:
        loop.close()

    return {
        "status": res.get("status", "SUCCESS"),
        "task_id": self.request.id,
        "job_id": job_id,
        "result": res
    }

@celery_app.task(bind=True, name="tasks.sync_emails")
def task_sync_emails(self) -> Dict[str, Any]:
    """Syncs incoming employer emails."""
    agent_logger.log_event("CELERY_WORKER", f"[Task {self.request.id}] Syncing incoming email queue...")
    from backend.app.modules.outcome.oauth_mail_agent import oauth_mail_agent

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(oauth_mail_agent.sync_emails())
    finally:
        loop.close()
    return {**result, "task_id": self.request.id}
