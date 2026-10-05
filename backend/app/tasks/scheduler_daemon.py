"""
Autonomous Background Scheduler & Nightly Sweep Daemon
Runs 24/7 background cron tasks:
- Nightly silent job portal scraping (03:30 AM)
- Morning Auto-Apply draft preparation (08:00 AM)
- Expired deadline sweep and closing-soon alerts
- Live status, pause/resume, and manual trigger controls
"""

import asyncio
from datetime import datetime, time
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo
from backend.app.core.config import settings
from backend.app.core.event_logger import agent_logger
from backend.app.core.ws_manager import ws_manager
from backend.app.modules.scrape.seen_jobs_tracker import seen_jobs_tracker
from backend.app.modules.scrape.unified_scraper import unified_scraper
from backend.app.modules.scrape.saved_search_service import run_enabled_saved_searches
from backend.app.modules.apply.auto_apply_pipeline import auto_apply_pipeline
from backend.app.modules.outcome.telegram_bot import telegram_dispatcher
from backend.app.core.tenant import get_tenant_id
from backend.app.core.database import use_tenant


MAX_SCAN_QUERIES = 4
_TASK_LINES = (
    ("inbox_reply", "yanıt bekleyen e-posta"),
    ("follow_up_due", "takip zamanı gelen başvuru"),
    ("confirm_submission", "portalda teyit bekleyen başvuru"),
    ("approve_draft", "onay bekleyen taslak"),
    ("closing_soon", "son başvuru tarihi yaklaşan ilan"),
    ("interview_prep", "hazırlanılacak mülakat"),
    ("offer_review", "değerlendirilecek teklif"),
)


def scan_queries(profile: Dict[str, Any]) -> List[str]:
    """What the overnight scan searches for: the candidate's own target roles, not a fixed keyword."""
    roles = [profile.get("target_role"), *(profile.get("target_roles") or [])]
    queries = list(dict.fromkeys(str(role).strip() for role in roles if str(role or "").strip()))
    return queries[:MAX_SCAN_QUERIES] or [settings.DEFAULT_SCRAPE_QUERY]


def morning_message(prepared_count: int, today: Dict[str, Any]) -> Optional[str]:
    """The morning Telegram summary; None when there is nothing worth a notification."""
    counts = today.get("counts") or {}
    lines = [f"• {counts[kind]} {label}" for kind, label in _TASK_LINES if counts.get(kind)]
    new_matches = next((action.get("count") for action in today.get("actions") or [] if action.get("kind") == "new_matches"), 0)
    if new_matches:
        lines.append(f"• {new_matches} yeni yüksek uyumlu ilan")
    if not lines and not prepared_count:
        return None
    header = "🌅 *Günaydın! Bugünün işleri*"
    if prepared_count:
        header += f"\n{prepared_count} ilan için başvuru taslağı hazırlandı."
    return "\n".join([header, *lines, "Ayrıntılar panelin ana sayfasında."])


def _scheduled_tenants():
    tenant_id = get_tenant_id()
    if tenant_id or not settings.MULTI_TENANT_ENABLED:
        return [tenant_id]
    from backend.app.core.auth_sessions import list_active_tenant_ids
    return list_active_tenant_ids()


class AutonomousSchedulerDaemon:
    """Manages continuous background task execution and heartbeat monitoring."""

    def __init__(self):
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._run_lock = asyncio.Lock()
        self.last_nightly_run: Optional[str] = None
        self.last_morning_run: Optional[str] = None
        self.last_follow_up_run: Optional[str] = None
        self.total_cycles = 0
        self.last_error: Optional[str] = None

    def get_status(self) -> Dict[str, Any]:
        """Returns daemon state and execution history."""
        return {
            "is_running": self.is_running,
            "total_cycles_executed": self.total_cycles,
            "last_nightly_run": self.last_nightly_run or "Henüz çalışmadı",
            "last_morning_run": self.last_morning_run or "Henüz çalışmadı",
            "last_follow_up_run": self.last_follow_up_run or "Henüz çalışmadı",
            "last_error": self.last_error,
            "timezone": settings.SCHEDULER_TIMEZONE,
            "active_schedules": [
                {"name": "Nightly Silent Scrape", "time": settings.SCHEDULER_NIGHTLY_TIME, "purpose": "Tüm portalları sessizce tarar ve dedup listesine ekler"},
                {"name": "Morning Auto-Apply Prep", "time": settings.SCHEDULER_MORNING_TIME, "purpose": "Yüksek uyumlu ilanların Drafter-Reviewer taslaklarını hazırlar"},
                {"name": "Follow-up Reminders", "interval": "15 dakikada bir", "purpose": "Başvuru takip zamanı gelen kayıtlar için tekrarsız panel bildirimi oluşturur"}
            ]
        }

    @staticmethod
    def _schedule_time(value: str, fallback: time) -> time:
        try:
            hour, minute = (int(part) for part in value.strip().split(":", 1))
            return time(hour=hour, minute=minute)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _now() -> datetime:
        try:
            return datetime.now(ZoneInfo(settings.SCHEDULER_TIMEZONE))
        except Exception:
            return datetime.now()

    async def trigger_nightly_sweep(self) -> Dict[str, Any]:
        tenants = _scheduled_tenants()
        if len(tenants) != 1 or (tenants and tenants[0] is not None):
            results = {}
            for tenant_id in tenants:
                with use_tenant(tenant_id):
                    results[tenant_id] = await self._trigger_nightly_sweep_for_current_tenant()
            return {"status": "success", "tenants_processed": len(results), "results": results}
        return await self._trigger_nightly_sweep_for_current_tenant()

    async def _trigger_nightly_sweep_for_current_tenant(self) -> Dict[str, Any]:
        """Executes nightly portal scraping sweep."""
        async with self._run_lock:
            self.last_nightly_run = self._now().isoformat()
            self.last_error = None
            agent_logger.log_event("DAEMON", "Nightly silent sweep triggered.")

            try:
                # Keep network-bound scraping off the event loop. The daemon is
                # opt-in and this is the only scheduled path that performs the
                # overnight scan.
                from backend.app.api.profile import fetch_candidate_profile
                from backend.app.modules.rank.llm_reranker import review_top_jobs
                from backend.app.modules.rank.scoring_engine import rank_and_save_all_jobs

                profile = await asyncio.to_thread(fetch_candidate_profile)
                scrape_result = await asyncio.to_thread(
                    unified_scraper.run_multi_platform_scrape,
                    queries=scan_queries(profile),
                )
                # Score what was just found; the morning prep picks drafts by these scores.
                await asyncio.to_thread(rank_and_save_all_jobs, profile)
                ai_review = await review_top_jobs(profile)
                saved_search_results = await asyncio.to_thread(
                    run_enabled_saved_searches
                )

                expired = await asyncio.to_thread(
                    seen_jobs_tracker.sweep_expired,
                    dry_run=False,
                )
                closing_soon = await asyncio.to_thread(
                    seen_jobs_tracker.get_closing_soon,
                    days=3,
                )

                result = {
                    "status": "success",
                    "scraped_count": scrape_result.get("total_scraped", 0),
                    "saved_searches_run": len(saved_search_results),
                    "saved_search_matches": sum(item.get("new_matches", 0) for item in saved_search_results),
                    "expired_cleaned": len(expired),
                    "closing_soon_count": len(closing_soon),
                    "ai_reviewed": ai_review.get("reviewed", 0),
                }
                await ws_manager.broadcast("daemon_event", {
                    "action": "nightly_sweep_completed",
                    **result,
                    "timestamp": self.last_nightly_run,
                })
                return result
            except Exception as exc:
                self.last_error = str(exc)
                agent_logger.log_event("DAEMON_ERROR", f"Nightly sweep failed: {exc}")
                await ws_manager.broadcast("daemon_event", {
                    "action": "nightly_sweep_failed",
                    "error": self.last_error,
                    "timestamp": self.last_nightly_run,
                })
                return {"status": "error", "error": self.last_error}

    async def trigger_morning_prep(self) -> Dict[str, Any]:
        tenants = _scheduled_tenants()
        if len(tenants) != 1 or (tenants and tenants[0] is not None):
            results = {}
            for tenant_id in tenants:
                with use_tenant(tenant_id):
                    results[tenant_id] = await self._trigger_morning_prep_for_current_tenant()
            return {"status": "success", "tenants_processed": len(results), "results": results}
        return await self._trigger_morning_prep_for_current_tenant()

    async def _trigger_morning_prep_for_current_tenant(self) -> Dict[str, Any]:
        """Prepares high-match auto-apply drafts and notifies via Telegram."""
        async with self._run_lock:
            self.last_morning_run = self._now().isoformat()
            self.last_error = None
            agent_logger.log_event("DAEMON", "Morning auto-apply prep triggered.")

            try:
                prep_result = await auto_apply_pipeline.scan_and_prepare(
                    min_score=settings.MORNING_MIN_MATCH_SCORE,
                    max_daily_limit=settings.MORNING_DRAFT_LIMIT,
                    auto_request_approval=True,
                )

                await ws_manager.broadcast("daemon_event", {
                    "action": "morning_prep_completed",
                    "prepared_count": prep_result.get("prepared_count", 0),
                    "timestamp": self.last_morning_run,
                })

                from backend.app.modules.outcome.today import get_today_actions

                message = morning_message(prep_result.get("prepared_count", 0), await asyncio.to_thread(get_today_actions))
                if telegram_dispatcher.is_configured() and message:
                    try:
                        await telegram_dispatcher.send_notification(message)
                    except Exception as exc:
                        agent_logger.log_event("DAEMON_ERROR", f"Telegram morning notification failed: {exc}")

                return prep_result
            except Exception as exc:
                self.last_error = str(exc)
                agent_logger.log_event("DAEMON_ERROR", f"Morning prep failed: {exc}")
                await ws_manager.broadcast("daemon_event", {
                    "action": "morning_prep_failed",
                    "error": self.last_error,
                    "timestamp": self.last_morning_run,
                })
                return {"status": "error", "error": self.last_error, "prepared_count": 0}

    async def start_daemon(self):
        """Starts background loop if not already running."""
        if self.is_running:
            return {"status": "already_running"}

        self.is_running = True
        self._task = asyncio.create_task(self._daemon_loop())
        agent_logger.log_event("DAEMON", "Autonomous daemon started successfully.")
        return {"status": "started"}

    async def stop_daemon(self):
        """Stops background loop."""
        if not self.is_running:
            return {"status": "not_running"}

        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        agent_logger.log_event("DAEMON", "Autonomous daemon stopped.")
        return {"status": "stopped"}

    async def trigger_follow_up_reminders(self) -> Dict[str, Any]:
        """Persist due reminders in each active tenant's own notification store."""
        from backend.app.modules.outcome.follow_up_cadence import FollowUpCadenceEngine

        tenants = _scheduled_tenants()
        created = 0
        for tenant_id in tenants:
            try:
                if tenant_id is None:
                    created += await asyncio.to_thread(FollowUpCadenceEngine.emit_due_follow_up_notifications)
                else:
                    with use_tenant(tenant_id):
                        created += await asyncio.to_thread(FollowUpCadenceEngine.emit_due_follow_up_notifications)
            except Exception as exc:
                self.last_error = str(exc)
                agent_logger.log_event("DAEMON_ERROR", f"Follow-up reminder sweep failed: {exc}")
        self.last_follow_up_run = self._now().isoformat()
        return {"status": "success", "tenants_processed": len(tenants), "notifications_created": created}

    async def run_follow_up_reminder_loop(self) -> None:
        """Run reminder delivery independently of optional scraping automations."""
        while True:
            try:
                await self.trigger_follow_up_reminders()
            except Exception as exc:
                self.last_error = str(exc)
                agent_logger.log_event("DAEMON_ERROR", f"Follow-up reminder loop failed: {exc}")
            await asyncio.sleep(900)

    async def _daemon_loop(self):
        """Internal continuous loop monitoring schedule times."""
        try:
            while self.is_running:
                now = self._now()
                self.total_cycles += 1

                nightly_time = self._schedule_time(settings.SCHEDULER_NIGHTLY_TIME, time(3, 30))
                morning_time = self._schedule_time(settings.SCHEDULER_MORNING_TIME, time(8, 0))

                if now.hour == nightly_time.hour and now.minute == nightly_time.minute and (not self.last_nightly_run or self.last_nightly_run[:10] != now.strftime("%Y-%m-%d")):
                    await self.trigger_nightly_sweep()

                if now.hour == morning_time.hour and now.minute == morning_time.minute and (not self.last_morning_run or self.last_morning_run[:10] != now.strftime("%Y-%m-%d")):
                    await self.trigger_morning_prep()

                await asyncio.sleep(max(5, settings.DAEMON_POLL_SECONDS))
        except asyncio.CancelledError:
            self.is_running = False
        except Exception as exc:
            self.is_running = False
            self.last_error = str(exc)
            agent_logger.log_event("DAEMON_ERROR", f"Scheduler loop stopped unexpectedly: {exc}")


scheduler_daemon = AutonomousSchedulerDaemon()
