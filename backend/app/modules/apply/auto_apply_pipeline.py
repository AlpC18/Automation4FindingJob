"""
Autonomous Auto-Apply Pipeline with Human-in-the-Loop Approval Queue
Coordinates:
- Candidate job selection (Scored & ATS Matched >= threshold)
- Drafter-Reviewer agentic CV/Cover Letter generation
- Approval queue management (pending, approved, rejected, applied)
- Multi-channel notification (Telegram dispatch + Real-time WebSocket event)
- Rate limiting and daily safety controls
"""

import logging
import json
from datetime import datetime, date
from pathlib import Path
from backend.app.core.json_store import read_json_store
from typing import Dict, Any, List, Optional

from backend.app.core.config import settings
from backend.app.core.event_logger import agent_logger
from backend.app.core.ws_manager import ws_manager
from backend.app.core.tenant import get_tenant_id, tenant_data_path
from backend.app.modules.scrape.seen_jobs_tracker import seen_jobs_tracker
from backend.app.modules.apply.agentic_workflow import drafter_reviewer_pipeline
from backend.app.modules.outcome.telegram_bot import telegram_dispatcher
from backend.app.modules.outcome.kanban_manager import kanban_manager
from backend.app.tasks.job_store import create_job, update_job

logger = logging.getLogger(__name__)

QUEUE_FILE = settings.DATA_PATH / "auto_apply_queue.json"

class AutoApplyPipeline:
    """Orchestrates human-in-the-loop autonomous job submissions."""

    def __init__(self, queue_path: Path = QUEUE_FILE):
        self.queue_path = queue_path
        self._queues: Dict[str, Dict[str, Any]] = {}
        self._loaded_scopes = set()

    def _scope(self):
        return get_tenant_id() or "__shared__"

    def _scoped_queue_path(self):
        return tenant_data_path(self.queue_path.name) if get_tenant_id() else self.queue_path

    @property
    def _queue(self):
        scope = self._scope()
        if scope not in self._loaded_scopes:
            path = self._scoped_queue_path()
            value = read_json_store(path, {})
            self._queues[scope] = {"applications": {}, "daily_stats": {}, **value}
            self._loaded_scopes.add(scope)
        return self._queues[scope]

    @_queue.setter
    def _queue(self, value):
        scope = self._scope()
        self._queues[scope] = value
        self._loaded_scopes.add(scope)

    def _load(self):
        self._queue = read_json_store(self.queue_path, {"applications": {}, "daily_stats": {}})

    def _save(self):
        path = self._scoped_queue_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self._queue, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def get_today_count(self) -> int:
        """Returns number of applied or queued jobs today."""
        today = date.today().isoformat()
        return self._queue.get("daily_stats", {}).get(today, 0)

    def _increment_today_count(self):
        today = date.today().isoformat()
        if "daily_stats" not in self._queue:
            self._queue["daily_stats"] = {}
        self._queue["daily_stats"][today] = self._queue["daily_stats"].get(today, 0) + 1

    async def scan_and_prepare(
        self,
        min_score: int = 75,
        max_daily_limit: int = 5,
        auto_request_approval: bool = True
    ) -> Dict[str, Any]:
        """
        Scans for high-matching ranked jobs and prepares application drafts.
        Pushes them to the pending approval queue.
        """
        all_jobs = seen_jobs_tracker.get_all()
        candidates = []
        today_applied = self.get_today_count()

        if today_applied >= max_daily_limit:
            return {
                "status": "rate_limited",
                "message": f"Daily auto-apply limit ({max_daily_limit}) reached today ({today_applied}).",
                "prepared_count": 0
            }

        existing_in_queue = set(self._queue.get("applications", {}).keys())

        for key, job in all_jobs.items():
            if key in existing_in_queue:
                continue
            if job.get("status") in ("applied", "skipped", "expired"):
                continue

            score = job.get("match_score", 0)
            if score >= min_score:
                candidates.append((key, job))

        candidates.sort(key=lambda x: x[1].get("match_score", 0), reverse=True)
        available_slots = max(0, max_daily_limit - today_applied)
        selected = candidates[:available_slots]

        prepared_jobs = []
        for key, job in selected:
            agent_logger.log_event("AUTO_APPLY", f"Preparing draft application for {job.get('company')} - {job.get('title')}")
            
            # Run Drafter-Reviewer Agentic Workflow
            draft_result = await drafter_reviewer_pipeline.run_pipeline(
                job_data=job,
                max_revisions=1
            )

            app_entry = {
                "job_key": key,
                "company": job.get("company"),
                "title": job.get("title"),
                "location": job.get("location"),
                "url": job.get("url"),
                "match_score": job.get("match_score"),
                "prepared_at": datetime.now().isoformat(),
                "status": "pending_approval",
                "draft_result": draft_result
            }

            self._queue["applications"][key] = app_entry
            prepared_jobs.append(app_entry)

            # Broadcast real-time WebSocket event
            await ws_manager.broadcast("auto_apply_draft_ready", {
                "key": key,
                "company": job.get("company"),
                "title": job.get("title"),
                "score": job.get("match_score")
            })

            # Telegram push notification
            if auto_request_approval and telegram_dispatcher.is_configured():
                try:
                    await telegram_dispatcher.send_notification(
                        f"🎯 *Yeni Otomatik Başvuru Onayı Bekliyor*\n\n"
                        f"🏢 *Şirket:* {job.get('company')}\n"
                        f"💼 *Pozisyon:* {job.get('title')}\n"
                        f"📊 *ATS Skoru:* %{job.get('match_score')}\n\n"
                        f"Web panelinden onaylayıp iletebilirsiniz."
                    )
                except Exception:
                    logger.warning("Could not send the draft notification.", exc_info=True)

        self._save()

        return {
            "status": "success",
            "prepared_count": len(prepared_jobs),
            "prepared_jobs": prepared_jobs
        }

    async def approve_application(self, job_key: str) -> Dict[str, Any]:
        """Approves a draft without falsely claiming that a portal submission happened."""
        app = self._queue.get("applications", {}).get(job_key)
        if not app:
            return {"success": False, "error": "Application not found in queue"}

        app["status"] = "approved"
        app["approved_at"] = datetime.now().isoformat()
        self._save()

        await ws_manager.broadcast("auto_apply_status_changed", {
            "job_key": job_key,
            "status": "approved",
            "company": app.get("company"),
            "title": app.get("title")
        })

        agent_logger.log_event("AUTO_APPLY", f"Application approved for {app.get('company')}; submission still pending")
        return {"success": True, "application": app, "submission_confirmed": False}

    async def submit_approved_application(self, job_key: str, headless: bool = True) -> Dict[str, Any]:
        """Prepare a user-reviewed portal handoff; never click or claim an external submission."""
        app = self._queue.get("applications", {}).get(job_key)
        if not app:
            return {"success": False, "error": "Application not found in queue"}
        if app.get("status") != "approved":
            return {"success": False, "error": "Application must be approved first"}

        job, created = create_job(
            "application_handoff",
            {"job_key": job_key, "headless": headless},
            idempotency_key=f"application-submit:{job_key}",
        )
        if not created and job["status"] in {"queued", "running", "retrying", "succeeded"}:
            return {"success": job["status"] == "succeeded", "job_id": job["id"], "status": job["status"], "result": job.get("result_json")}

        update_job(job["id"], "running", increment_attempt=True)
        try:
            result = {
                "status": "USER_ACTION_REQUIRED",
                "url": app.get("url"),
                "applied": False,
                "submission_confirmed": False,
                "message": "Taslak hazır. Başvuruyu iş portalında kendin tamamla; ardından uygulamada gönderimi onayla.",
            }
        except Exception as exc:
            update_job(job["id"], "failed", error=str(exc))
            raise
        app["submission_result"] = result
        if result.get("submission_confirmed") is True:
            app["status"] = "applied"
            app["applied_at"] = datetime.now().isoformat()
            self._increment_today_count()
            seen_jobs_tracker.mark_applied(
                job_key,
                notes="Confirmed by browser submission workflow",
                confirmed=True,
            )
            app["kanban_sync"] = kanban_manager.confirm_submission_by_identity(
                job_key=job_key,
                url=app.get("url"),
                title=app.get("title"),
                company=app.get("company"),
                execution_mode="live",
            )
        else:
            app["status"] = "awaiting_user_submission"
        self._save()
        update_job(job["id"], "succeeded", result={"submission_confirmed": False, "job_key": job_key, "handoff_required": True})
        return {"success": True, "job_id": job["id"], "application": app, "submission_confirmed": False, "handoff_required": True}

    def confirm_manual_submission(self, job_key: str) -> Dict[str, Any]:
        """Record the candidate's explicit confirmation after they submit in the portal."""
        app = self._queue.get("applications", {}).get(job_key)
        if not app:
            return {"success": False, "error": "Application not found in queue"}
        if app.get("status") != "awaiting_user_submission":
            return {"success": False, "error": "Open the portal and complete the application before confirming it"}
        sync = kanban_manager.confirm_submission_by_identity(
            job_key=job_key,
            url=app.get("url"),
            title=app.get("title"),
            company=app.get("company"),
            execution_mode="live",
            message="Candidate explicitly confirmed submission in the external job portal.",
        )
        if not sync.get("submission_confirmed"):
            return {"success": False, "error": "Could not link this application to a saved job; it was not counted as submitted."}
        app["status"] = "applied"
        app["applied_at"] = datetime.now().isoformat()
        self._increment_today_count()
        seen_jobs_tracker.mark_applied(job_key, notes="Candidate confirmed live portal submission", confirmed=True)
        app["kanban_sync"] = sync
        self._save()
        return {"success": True, "application": app, "submission_confirmed": True}

    def reject_application(self, job_key: str, reason: str = "") -> Dict[str, Any]:
        """Rejects a prepared application draft."""
        app = self._queue.get("applications", {}).get(job_key)
        if not app:
            return {"success": False, "error": "Application not found in queue"}

        app["status"] = "rejected"
        app["rejected_at"] = datetime.now().isoformat()
        app["reject_reason"] = reason

        seen_jobs_tracker.mark_status(job_key, "skipped", notes=f"Auto-apply rejected: {reason}")
        self._save()

        ws_manager.broadcast_sync("auto_apply_status_changed", {
            "job_key": job_key,
            "status": "rejected"
        })

        return {"success": True, "application": app}

    def list_queue(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns queued applications, optionally filtered by status."""
        apps = list(self._queue.get("applications", {}).values())
        if status_filter:
            apps = [a for a in apps if a.get("status") == status_filter]
        apps.sort(key=lambda x: x.get("prepared_at", ""), reverse=True)
        return apps

auto_apply_pipeline = AutoApplyPipeline()
