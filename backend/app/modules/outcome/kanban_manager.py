"""
Kanban Pipeline & Human-in-the-Loop Application Manager
Manages job lifecycle states: Draft, Human Review, Applied, Interview, Offer, Rejected.
Enforces Human-in-the-Loop approval with Human Texture Score auditing.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from backend.app.core.database import get_db_connection
from backend.app.core.ws_manager import ws_manager
from backend.app.modules.scrape.rate_limiter import account_health
from backend.app.modules.scrape.seen_jobs_tracker import seen_jobs_tracker
from backend.app.modules.outcome.follow_up_scheduler import schedule_follow_ups_for_job
from backend.app.modules.outcome.today import next_steps
from backend.app.core.llm_client import is_template_engine

VALID_KANBAN_STAGES = ["Draft", "Human Review", "Applied", "Interview", "Offer", "Rejected"]

class KanbanManager:
    def get_kanban_board(self) -> Dict[str, List[Dict[str, Any]]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM scraped_jobs
            WHERE (stale_at IS NULL OR submission_confirmed = 1)
              AND (
                  COALESCE(status, 'Draft') NOT IN ('Draft', 'New', '')
                  OR COALESCE(cover_letter, '') <> ''
                  OR COALESCE(micro_portfolio, '') <> ''
              )
              AND (
                  COALESCE(status, 'Draft') NOT IN ('Interview', 'Offer')
                  OR COALESCE(submission_confirmed, 0) = 1
              )
            ORDER BY match_score DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        board = {stage: [] for stage in VALID_KANBAN_STAGES}
        for row in rows:
            item = dict(row)
            status = item.get("status", "Draft")
            if status not in board:
                status = "Draft"
            item["next_steps"] = next_steps(item)
            item["is_template_fallback"] = is_template_engine(item.get("draft_source"))
            board[status].append(item)
            
        return board

    def update_job_status(self, job_id: str, new_status: str) -> Dict[str, Any]:
        if new_status not in VALID_KANBAN_STAGES:
            raise ValueError(f"Invalid status: {new_status}. Must be one of {VALID_KANBAN_STAGES}")
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, company, url, platform FROM scraped_jobs WHERE id = ?", (job_id,))
        job_row = cursor.fetchone()
        
        applied_at = None
        if new_status == "Applied":
            cursor.execute("""
                UPDATE scraped_jobs
                SET status = ?, applied_at = NULL,
                    submission_state = 'pending_confirmation',
                    submission_confirmed = 0,
                    application_execution_mode = 'simulation',
                    submission_message = ?
                WHERE id = ?
            """, (
                new_status,
                "Kanban aşaması güncellendi; gerçek portal gönderimi henüz doğrulanmadı.",
                job_id,
            ))
        else:
            cursor.execute("UPDATE scraped_jobs SET status = ? WHERE id = ?", (new_status, job_id))
            
        conn.commit()
        conn.close()
        tracker_updated = False
        if job_row:
            tracker_key = seen_jobs_tracker.get_key(
                job_row["company"], job_row["title"], job_row["url"] or ""
            )
            if new_status == "Applied":
                tracker_updated = seen_jobs_tracker.mark_applied(
                    tracker_key,
                    notes="Kanban aşaması Applied; portal gönderimi doğrulama bekliyor.",
                    confirmed=False,
                )
            elif new_status in {"Interview", "Offer", "Rejected"}:
                tracker_updated = seen_jobs_tracker.mark_status(
                    tracker_key, new_status.lower(), notes="Kanban aşaması güncellendi."
                )

        ws_manager.broadcast_sync("kanban_stage_changed", {
            "job_id": job_id,
            "new_status": new_status,
            "submission_confirmed": False if new_status == "Applied" else None,
            "tracker_updated": tracker_updated,
        })
        return {
            "job_id": job_id,
            "new_status": new_status,
            "applied_at": applied_at,
            "submission_confirmed": False if new_status == "Applied" else None,
            "application_execution_mode": "simulation" if new_status == "Applied" else None,
            "tracker_updated": tracker_updated,
        }

    def confirm_submission(
        self,
        job_id: str,
        execution_mode: str = "live",
        message: str = "Portal başvurusu kullanıcı/portal doğrulamasıyla onaylandı.",
    ) -> Dict[str, Any]:
        """Record an externally verified submission as the only real apply state."""
        if execution_mode not in {"live", "simulation"}:
            raise ValueError("execution_mode live veya simulation olmalı.")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scraped_jobs WHERE id = ?", (job_id,))
        job_row = cursor.fetchone()
        if not job_row:
            conn.close()
            raise ValueError("Job not found")

        applied_at = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            UPDATE scraped_jobs
            SET status = 'Applied', applied_at = ?,
                submission_state = 'confirmed', submission_confirmed = 1,
                application_execution_mode = ?, submission_message = ?
            WHERE id = ?
        """, (applied_at, execution_mode, message, job_id))
        conn.commit()
        conn.close()

        tracker_key = seen_jobs_tracker.get_key(
            job_row["company"], job_row["title"], job_row["url"] or ""
        )
        tracker_updated = seen_jobs_tracker.mark_applied(
            tracker_key,
            notes=message,
            confirmed=True,
        )
        ws_manager.broadcast_sync("submission_confirmed", {
            "job_id": job_id,
            "new_status": "Applied",
            "submission_confirmed": True,
            "application_execution_mode": execution_mode,
        })

        account_health.log_action(
            job_row["platform"],
            "apply",
            "SUCCESS" if execution_mode == "live" else "SIMULATED",
            f"{execution_mode} application for {job_row['title']} @ {job_row['company']}",
        )
        # Follow-up automation is reserved for a real, externally confirmed
        # submission; simulation confirmation must not contact recruiters.
        if execution_mode == "live":
            schedule_follow_ups_for_job(dict(job_row))
        return {
            "job_id": job_id,
            "new_status": "Applied",
            "applied_at": applied_at,
            "submission_confirmed": True,
            "application_execution_mode": execution_mode,
            "submission_message": message,
            "tracker_updated": tracker_updated,
        }

    def confirm_submission_by_identity(
        self,
        job_key: Optional[str] = None,
        url: Optional[str] = None,
        title: Optional[str] = None,
        company: Optional[str] = None,
        execution_mode: str = "live",
        message: str = "Portal başvurusu auto-apply tarayıcı akışıyla doğrulandı.",
    ) -> Dict[str, Any]:
        """Resolve a tracker/queue identity and persist the same state in SQL."""
        conn = get_db_connection()
        cursor = conn.cursor()
        row = None
        if job_key:
            cursor.execute("SELECT * FROM scraped_jobs WHERE id = ? LIMIT 1", (job_key,))
            row = cursor.fetchone()
        if not row and url:
            cursor.execute(
                "SELECT * FROM scraped_jobs WHERE url = ? AND title = ? AND company = ? LIMIT 1",
                (url, title or "", company or ""),
            )
            row = cursor.fetchone()
        conn.close()
        if not row:
            return {
                "synced": False,
                "submission_confirmed": False,
                "message": "SQL Kanban kaydı bulunamadı; tracker durumu korunuyor.",
            }
        return {
            "synced": True,
            **self.confirm_submission(str(row["id"]), execution_mode, message),
        }

    def approve_human_in_the_loop(self, job_id: str, final_cover_letter: str = None) -> Dict[str, Any]:
        """
        Human reviewer approves the tailored materials and moves job from Human Review to Applied.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        if final_cover_letter:
            cursor.execute("UPDATE scraped_jobs SET cover_letter = ? WHERE id = ?", (final_cover_letter, job_id))
            conn.commit()
        conn.close()
        return self.update_job_status(job_id, "Applied")

kanban_manager = KanbanManager()
