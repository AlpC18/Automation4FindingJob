"""
Dual-Mode Task Dispatcher
Intelligently dispatches jobs to Celery + Redis when available,
or falls back smoothly to asyncio/FastAPI background tasks when in lightweight standalone mode.
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, Optional
from backend.app.core.config import settings
from backend.app.core.event_logger import agent_logger
from backend.app.tasks.celery_app import celery_app, check_redis_connection
from backend.app.tasks.job_store import create_job, get_job, get_job_stats, update_job

logger = logging.getLogger(__name__)

class TaskDispatcher:
    def __init__(self):
        self._local_tasks: set[asyncio.Task] = set()

    def is_celery_active(self) -> bool:
        """Returns True if Celery is enabled in config and Redis is pingable."""
        if not settings.USE_CELERY:
            return False
        return check_redis_connection()

    def get_queue_status(self) -> Dict[str, Any]:
        """Provides real-time health and diagnostics for the task queue."""
        redis_ok = check_redis_connection()
        workers = []
        if redis_ok:
            try:
                insp = celery_app.control.inspect(timeout=0.5)
                active = insp.active()
                if active:
                    workers = list(active.keys())
            except Exception:
                logger.warning("Could not inspect background workers.", exc_info=True)

        mode = "CELERY_REDIS" if (settings.USE_CELERY and redis_ok) else "ASYNC_LOCAL"

        return {
            "mode": mode,
            "use_celery_setting": settings.USE_CELERY,
            "redis_connected": redis_ok,
            "broker_url": settings.REDIS_URL,
            "active_workers": workers,
            "worker_count": len(workers),
            "durable_jobs": get_job_stats(),
            "description": "Enterprise Celery + Redis Dağıtık Kuyruk Aktif" if mode == "CELERY_REDIS" else "Hafif Hibrit Asenkron Kuyruk (Local AsyncIO)"
        }

    async def dispatch_scrape(
        self,
        keywords: str,
        location: str,
        limit: int = 15,
        tenant_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        scrape_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Dispatch a complete search request to a durable local/Celery job."""
        options = dict(scrape_options or {})
        run_options = {
            "query": keywords,
            "target_platforms": options.get("platforms"),
            "queries": options.get("queries"),
            "location_preference": options.get("location_preference") or location or None,
            "remote_type": options.get("remote_type"),
            "replace_current_feed": options.get("replace_current_feed", True),
        }
        payload = {"keywords": keywords, "location": location, "limit": limit, "scrape_options": run_options}
        job, created = create_job("scrape", payload, idempotency_key)
        if not created:
            return {
                "job_id": job["id"],
                "status": job["status"],
                "message": "Idempotent existing job returned; failed jobs can be retried explicitly.",
            }
        if self.is_celery_active():
            from backend.app.tasks.worker_tasks import task_scrape_jobs
            async_result = task_scrape_jobs.delay(
                keywords=keywords, location=location, limit=limit, tenant_id=tenant_id,
                job_id=job["id"], **run_options,
            )
            update_job(job["id"], "queued", celery_task_id=async_result.id)
            agent_logger.log_event("TASK_DISPATCHER", f"Dispatched scrape task {async_result.id} to Celery worker.")
            return {
                "dispatch_mode": "CELERY_REDIS",
                "task_id": async_result.id,
                "job_id": job["id"],
                "status": "QUEUED",
                "message": "Görev Redis kuyruğuna alındı ve Celery worker tarafından işleniyor."
            }
        # Keep local development durable too, but do not hold the HTTP request
        # open while external sources are being queried.
        task_id = f"local-{uuid.uuid4().hex[:8]}"
        self._schedule_local_scrape(job["id"], run_options, task_id)
        return {
            "dispatch_mode": "ASYNC_LOCAL",
            "task_id": task_id,
            "job_id": job["id"],
            "status": "QUEUED",
            "message": "Tarama yerel arka plan kuyruğuna alındı; durumunu iş kaydından takip edebilirsin."
        }

    def _schedule_local_scrape(self, job_id: str, run_options: Dict[str, Any], task_id: str) -> None:
        async def run():
            try:
                await asyncio.to_thread(self._execute_local_scrape, job_id, run_options, task_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # Keep task failures visible in the durable job record.
                update_job(job_id, "failed", error=str(exc))
                agent_logger.log_event("TASK_DISPATCHER", f"Local scrape task {task_id} failed: {exc}")

        task = asyncio.create_task(run(), name=f"scrape:{job_id}")
        self._local_tasks.add(task)
        task.add_done_callback(self._local_tasks.discard)

    @staticmethod
    def _execute_local_scrape(job_id: str, run_options: Dict[str, Any], task_id: str) -> None:
        from backend.app.modules.scrape.unified_scraper import unified_scraper

        agent_logger.log_event("TASK_DISPATCHER", f"Executing scrape task {task_id} in local background mode.")
        update_job(job_id, "running", increment_attempt=True)
        try:
            res = unified_scraper.run_multi_platform_scrape(**run_options)
            jobs = res.get("jobs", [])
            durable_result = {
                "count": res.get("total_scraped", len(jobs)),
                "current_total": res.get("current_total", 0),
                "newly_saved_count": res.get("newly_saved_count", 0),
                "scan_id": res.get("scan_id"),
                "errors": res.get("errors", []),
            }
            update_job(job_id, "succeeded", result=durable_result)
        except Exception as exc:
            update_job(job_id, "failed", error=str(exc))
            agent_logger.log_event("TASK_DISPATCHER", f"Local scrape task {task_id} failed: {exc}")

    async def retry_scrape(self, job_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        job = get_job(job_id)
        if not job:
            raise ValueError("Background job not found.")
        if job["status"] not in {"failed", "retrying"}:
            raise ValueError("Only failed or retrying jobs can be retried.")
        import json
        payload = json.loads(job.get("payload_json") or "{}")
        scrape_options = payload.get("scrape_options") or {
            "query": payload.get("keywords", ""),
            "location_preference": payload.get("location", "") or None,
        }
        if job.get("job_type") == "application_submit":
            from backend.app.modules.apply.auto_apply_pipeline import auto_apply_pipeline
            return await auto_apply_pipeline.submit_approved_application(
                payload.get("job_key", ""), headless=payload.get("headless", True)
            )
        if job.get("job_type") != "scrape":
            raise ValueError("This background job type cannot be retried through this endpoint.")
        if self.is_celery_active():
            from backend.app.tasks.worker_tasks import task_scrape_jobs
            task = task_scrape_jobs.delay(
                keywords=payload.get("keywords", ""), location=payload.get("location", ""),
                limit=payload.get("limit", 15), tenant_id=tenant_id, job_id=job_id,
                **scrape_options,
            )
            update_job(job_id, "queued", error=None, celery_task_id=task.id)
            return {"job_id": job_id, "task_id": task.id, "status": "queued"}
        task_id = f"local-{uuid.uuid4().hex[:8]}"
        update_job(job_id, "queued", error=None)
        self._schedule_local_scrape(job_id, scrape_options, task_id)
        return {
            "dispatch_mode": "ASYNC_LOCAL",
            "job_id": job_id,
            "task_id": task_id,
            "status": "queued",
            "message": "Başarısız tarama yerel arka plan kuyruğuna yeniden alındı.",
        }
    async def dispatch_stealth_apply(self, job_id: str, applicant_data: Dict[str, Any], headless: bool = True) -> Dict[str, Any]:
        """Dispatches Playwright Easy Apply task."""
        if self.is_celery_active():
            from backend.app.tasks.worker_tasks import task_stealth_apply
            async_result = task_stealth_apply.delay(job_id=job_id, applicant_data=applicant_data, headless=headless)
            agent_logger.log_event("TASK_DISPATCHER", f"Dispatched stealth apply task {async_result.id} to Celery worker.")
            return {
                "dispatch_mode": "CELERY_REDIS",
                "task_id": async_result.id,
                "status": "QUEUED",
                "message": "Playwright başvurusu Redis kuyruğuna iletildi."
            }
        else:
            from backend.app.modules.scrape.stealth_browser import stealth_worker
            from backend.app.core.database import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scraped_jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            conn.close()
            job_url = row["url"] if row and row["url"] else "https://www.linkedin.com/jobs"
            res = await stealth_worker.execute_easy_apply_flow(job_url, applicant_data, headless)
            return {
                "dispatch_mode": "ASYNC_LOCAL",
                "status": res.get("status", "SUCCESS"),
                "result": res
            }

task_dispatcher = TaskDispatcher()
