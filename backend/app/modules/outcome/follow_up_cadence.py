"""
Smart Follow-Up Cadence & Calendar Integration Engine
Automates post-application lifecycle:
- 3-touch follow-up cadence generation (Check-in, Value-Add, Break-up)
- Overdue follow-up detector based on application dates
- Interview event generation (.ics file format & direct Google Calendar deep link)
"""

import urllib.parse
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from backend.app.core.database import get_db_connection
from backend.app.api.profile import fetch_candidate_profile
from backend.app.core.config import settings
from backend.app.core.security_email import is_configured as smtp_is_configured, send_security_email

logger = logging.getLogger(__name__)

class FollowUpCadenceEngine:
    """Manages proactive application follow-up strategies and calendar sync."""

    def generate_cadence_messages(
        self,
        company: str,
        title: str,
        recruiter_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generates a 3-touch follow-up sequence with optimal timing."""
        recruiter = recruiter_name or "Hiring Team"

        touch_1 = (
            f"Subject: Following up on {title} application – {company}\n\n"
            f"Hi {recruiter},\n\n"
            f"I hope you're having a productive week. I recently submitted my application for the {title} position "
            f"and wanted to reiterate my interest in {company}. I would welcome the opportunity to discuss "
            f"my background and how it may align with the role's needs.\n\n"
            f"Best regards,"
        )

        touch_2 = (
            f"Subject: Following up on {title} – {company}\n\n"
            f"Hi {recruiter},\n\n"
            f"Following up on my previous note about the {title} position. I would be glad to discuss my experience "
            f"and answer any questions the team may have.\n\n"
            f"Would you be open to a brief introductory call?\n\n"
            f"Best regards,"
        )

        touch_3 = (
            f"Subject: Closing the loop – {title} application\n\n"
            f"Hi {recruiter},\n\n"
            f"I understand your team is likely busy reviewing candidates for the {title} role. "
            f"I'll assume you have moved forward with other applicants for now and will close the loop on my end. "
            f"Should circumstances change, please feel free to reach back out.\n\n"
            f"Wishing {company} continued success!\n\n"
            f"Best regards,"
        )

        return {
            "company": company,
            "title": title,
            "cadence": [
                {"stage": "Touch 1 (Day 4)", "timing_days": 4, "purpose": "Polite check-in & interest confirmation", "body": touch_1},
                {"stage": "Touch 2 (Day 9)", "timing_days": 9, "purpose": "Experience discussion", "body": touch_2},
                {"stage": "Touch 3 (Day 14)", "timing_days": 14, "purpose": "Professional close-the-loop / breakup email", "body": touch_3},
            ]
        }

    def get_pending_follow_ups(self) -> List[Dict[str, Any]]:
        """Return only durable, confirmed submissions whose follow-up date has arrived."""
        self.emit_due_follow_up_notifications()
        conn = get_db_connection()
        try:
            rows = conn.cursor().execute(
                """SELECT f.id AS follow_up_id, f.job_id, f.due_day, f.scheduled_date, j.title, j.company,
                          j.applied_at, j.platform
                   FROM follow_up_queue f
                   JOIN scraped_jobs j ON j.id = f.job_id
                   WHERE f.status = 'PENDING'
                     AND f.scheduled_date <= ?
                     AND j.status = 'Applied'
                     AND COALESCE(j.submission_confirmed, 0) = 1
                   ORDER BY f.scheduled_date ASC, f.due_day ASC""",
                (datetime.now(timezone.utc).date().isoformat(),),
            ).fetchall()
        finally:
            conn.close()

        now = datetime.now(timezone.utc)
        pending_by_job = {}
        for row in rows:
            job_id = row["job_id"]
            applied_value = row["applied_at"] or row["scheduled_date"]
            try:
                applied_at = datetime.fromisoformat(str(applied_value).replace("Z", "+00:00"))
                if applied_at.tzinfo is None:
                    applied_at = applied_at.replace(tzinfo=timezone.utc)
                days_elapsed = max(0, (now - applied_at.astimezone(timezone.utc)).days)
            except (TypeError, ValueError):
                days_elapsed = int(row["due_day"])
            item = pending_by_job.setdefault(job_id, {
                "job_key": job_id,
                "company": row["company"],
                "title": row["title"],
                "platform": row["platform"],
                "days_since_applied": days_elapsed,
                "due_days": [],
                "follow_up_ids": [],
                "cadence": self.generate_cadence_messages(row["company"] or "", row["title"] or "")["cadence"],
            })
            item["due_days"].append(int(row["due_day"]))
            item["follow_up_ids"].append(int(row["follow_up_id"]))
        pending = list(pending_by_job.values())
        pending.sort(key=lambda item: item["days_since_applied"], reverse=True)
        return pending

    @staticmethod
    def emit_due_follow_up_notifications() -> int:
        """Create one durable in-app reminder per due follow-up, without emailing recruiters."""
        profile = fetch_candidate_profile()
        email_reminders_enabled = bool(
            profile.get("follow_up_email_reminders")
            and profile.get("email")
            and smtp_is_configured()
        )
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            rows = cursor.execute(
                """SELECT f.id, f.job_id, f.due_day, j.title, j.company
                   FROM follow_up_queue f
                   JOIN scraped_jobs j ON j.id = f.job_id
                   WHERE f.status = 'PENDING'
                     AND f.scheduled_date <= ?
                     AND j.status = 'Applied'
                     AND COALESCE(j.submission_confirmed, 0) = 1""",
                (datetime.now(timezone.utc).date().isoformat(),),
            ).fetchall()
            created = 0
            for row in rows:
                cursor.execute(
                    """INSERT INTO user_notifications(id, title, body, href)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(id) DO NOTHING""",
                    (
                        f"follow-up-{row['id']}",
                        f"{int(row['due_day'])}. gün başvuru takibi zamanı",
                        f"{row['company']} — {row['title']} başvurusu için takip taslağını gözden geçirebilirsin.",
                        f"/follow-up?job_id={row['job_id']}",
                    ),
                )
                created += max(0, cursor.rowcount)
                if email_reminders_enabled:
                    retry_before = (datetime.now(timezone.utc) - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute(
                        """UPDATE follow_up_queue SET email_claimed_at = CURRENT_TIMESTAMP
                           WHERE id = ? AND email_notified_at IS NULL
                             AND (email_claimed_at IS NULL OR email_claimed_at < ?)""",
                        (row["id"], retry_before),
                    )
                    if cursor.rowcount > 0:
                        conn.commit()
                        due_day = int(row["due_day"])
                        body = (
                            f"{row['company']} şirketindeki {row['title']} başvurun için "
                            f"{due_day}. gün takip hatırlatması geldi.\n\n"
                            "Bu yalnızca sana gönderilen bir hatırlatmadır; işverene e-posta gönderilmedi. "
                            f"Taslağı gözden geçir: {settings.FRONTEND_PUBLIC_URL}/follow-up?job_id={row['job_id']}"
                        )
                        try:
                            send_security_email(
                                profile["email"],
                                f"Başvuru takip hatırlatması — {row['company']}",
                                body,
                            )
                        except Exception:
                            cursor.execute(
                                "UPDATE follow_up_queue SET email_claimed_at = NULL WHERE id = ? AND email_notified_at IS NULL",
                                (row["id"],),
                            )
                            conn.commit()
                            logger.exception("Could not send opted-in follow-up reminder email for queue item %s", row["id"])
                        else:
                            cursor.execute(
                                "UPDATE follow_up_queue SET email_notified_at = CURRENT_TIMESTAMP, email_claimed_at = NULL WHERE id = ?",
                                (row["id"],),
                            )
                            conn.commit()
            conn.commit()
            return created
        finally:
            conn.close()

    def generate_google_calendar_url(
        self,
        title: str,
        company: str,
        interview_time_iso: str,
        duration_minutes: int = 45,
        meeting_link: str = ""
    ) -> str:
        """Creates an instant 1-click Google Calendar add link."""
        try:
            start_dt = datetime.fromisoformat(interview_time_iso.replace("Z", ""))
        except Exception:
            start_dt = datetime.now() + timedelta(days=1)

        end_dt = start_dt + timedelta(minutes=duration_minutes)
        fmt = "%Y%m%dT%H%M%SZ"

        event_title = f"Interview: {company} – {title}"
        details = f"Role: {title}\nCompany: {company}\nMeeting Link: {meeting_link}\n\nPrepared with Autonomous Career Agent"
        
        params = {
            "action": "TEMPLATE",
            "text": event_title,
            "dates": f"{start_dt.strftime(fmt)}/{end_dt.strftime(fmt)}",
            "details": details,
            "location": meeting_link or "Online Video Call"
        }

        return f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(params)}"

follow_up_cadence_engine = FollowUpCadenceEngine()
