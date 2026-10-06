"""
Inbox Automation & Autonomous Scheduler Agent
Listens to and classifies incoming employer emails:
1. REJECTION -> Moves Kanban job to 'Rejected', logs reason.
2. INTERVIEW_INVITE -> Detects Calendly/Meet URLs, suggests calendar slots, alerts candidate.
3. TECHNICAL_ASSESSMENT -> Identifies take-home tasks and deadlines.
4. ADDITIONAL_INFO -> Queries Form Memory to draft immediate reply.
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from backend.app.core.database import get_db_connection, is_postgres_database
from backend.app.core.event_logger import agent_logger
from backend.app.modules.outcome.kanban_manager import kanban_manager
from backend.app.modules.apply.email_finder import email_finder

class InboxAutomationAgent:
    def classify_email(self, subject: str, body: str) -> Dict[str, Any]:
        text = f"{subject}\n{body}".lower()
        meet_link = self._extract_meeting_link(body)

        # 1. Interview Invitation
        interview_keywords = ["interview", "invitation", "schedule a call", "speak with our team", "next steps", "mülakat", "görüşme", "calendly", "zoom.us", "meet.google"]
        if any(kw in text for kw in interview_keywords) and not ("unfortunately" in text or "not selected" in text):
            # Propose 3 calendar availability slots
            tomorrow = datetime.now() + timedelta(days=1)
            slot1 = f"{tomorrow.strftime('%A')} 14:00 CET"
            slot2 = f"{(tomorrow + timedelta(days=1)).strftime('%A')} 11:00 CET"
            slot3 = f"{(tomorrow + timedelta(days=2)).strftime('%A')} 16:30 CET"
            
            proposed_reply = (
                f"Thank you for the invitation! I would be delighted to speak with your team.\n\n"
                f"The following times work well for me:\n"
                f"1. {slot1}\n"
                f"2. {slot2}\n"
                f"3. {slot3}\n\n"
                f"Looking forward to our conversation.\n\nBest regards,\nCandidate"
            )
            return {
                "classification": "INTERVIEW_INVITE",
                "label": "Mülakat Daveti 🎉",
                "confidence": 0.95,
                "meet_link": meet_link,
                "proposed_reply": proposed_reply,
                "action_recommended": "SCHEDULE_CALL"
            }

        # 2. Rejection
        rejection_keywords = ["unfortunately", "other candidates", "not moving forward", "not selected", "regret to inform", "maalesef", "olumsuz", "başka adaylar"]
        if any(kw in text for kw in rejection_keywords):
            return {
                "classification": "REJECTION",
                "label": "Olumsuz Geri Dönüş (Ret)",
                "confidence": 0.92,
                "meet_link": None,
                "proposed_reply": (
                    "Thank you for letting me know. I appreciated learning more about your team and hope to stay in touch for future opportunities."
                ),
                "action_recommended": "ARCHIVE_JOB"
            }

        # 3. Technical Assessment
        tech_keywords = ["take-home", "coding challenge", "hackerrank", "coderbyte", "assessment", "teknik ödev", "proje ödevi"]
        if any(kw in text for kw in tech_keywords):
            return {
                "classification": "TECHNICAL_ASSESSMENT",
                "label": "Teknik Case / Değerlendirme",
                "confidence": 0.88,
                "meet_link": meet_link,
                "proposed_reply": (
                    "Thank you for sharing the assessment details. I have received the challenge and will complete and submit it before the specified deadline."
                ),
                "action_recommended": "REVIEW_TASK"
            }

        # 4. Additional Information Required
        return {
            "classification": "ADDITIONAL_INFO",
            "label": "Ek Bilgi / Soru Talebi",
            "confidence": 0.75,
            "meet_link": meet_link,
            "proposed_reply": "Thank you for reaching out. Please find the requested details attached.",
            "action_recommended": "REVIEW_REPLY"
        }

    def _extract_meeting_link(self, text: str) -> Optional[str]:
        # Regex for common video conference URLs
        match = re.search(r"https?://(?:[a-zA-Z0-9-]+\.)?(?:zoom\.us/j/[^\s]+|meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}|calendly\.com/[^\s]+)", text)
        return match.group(0) if match else None

    async def ingest_incoming_email(
        self,
        sender_email: str,
        sender_name: str,
        subject: str,
        body_text: str,
        job_id: Optional[str] = None,
        source_provider: Optional[str] = None,
        external_message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Parses incoming employer email, records in DB, updates Kanban state machine, and triggers alerts.
        """
        analysis = self.classify_email(subject, body_text)
        
        # Match job by company name in subject/sender if job_id not explicitly given
        matched_job_id = job_id
        conn = get_db_connection()
        cursor = conn.cursor()

        if source_provider and external_message_id:
            cursor.execute(
                "SELECT id, classification, detected_meet_url, proposed_reply, job_id "
                "FROM inbox_messages WHERE source_provider = ? AND external_message_id = ?",
                (source_provider, external_message_id),
            )
            existing = cursor.fetchone()
            if existing:
                conn.close()
                return {
                    "message_id": existing["id"],
                    "classification": existing["classification"],
                    "label": "Daha önce işlendi",
                    "meet_link": existing["detected_meet_url"],
                    "proposed_reply": existing["proposed_reply"],
                    "matched_job_id": existing["job_id"],
                    "duplicate": True,
                }

        if not matched_job_id:
            if is_postgres_database():
                cursor.execute(
                    "SELECT id FROM scraped_jobs WHERE position(lower(company) in lower(?)) > 0 LIMIT 1",
                    (f"{subject} {sender_email}",),
                )
            else:
                cursor.execute("SELECT id FROM scraped_jobs WHERE instr(lower(?), lower(company)) > 0 LIMIT 1", (f"{subject} {sender_email}",))
            row = cursor.fetchone()
            if row:
                matched_job_id = row["id"]

        # Insert message
        insert_sql = """
            INSERT INTO inbox_messages (
            job_id, sender_email, sender_name, subject, body_text,
                classification, detected_meet_url, proposed_reply, status,
                source_provider, external_message_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'UNREAD', ?, ?)
        """
        if is_postgres_database():
            insert_sql += " RETURNING id"
        cursor.execute(insert_sql, (
            matched_job_id, sender_email, sender_name, subject, body_text,
            analysis["classification"], analysis["meet_link"], analysis["proposed_reply"],
            source_provider or "", external_message_id or ""
        ))
        msg_id = cursor.fetchone()["id"] if is_postgres_database() else cursor.lastrowid
        conn.commit()

        # Autonomous Kanban State Transitions
        if matched_job_id:
            if analysis["classification"] == "INTERVIEW_INVITE":
                kanban_manager.update_job_status(matched_job_id, "Interview")
                agent_logger.log_event("INBOX_AGENT", f"Autonomous transition: Job {matched_job_id} moved to 'Interview'.")
                # Trigger Telegram Alert
                from backend.app.modules.outcome.telegram_bot import telegram_bot
                await telegram_bot.send_interview_alert(
                    company=sender_name or sender_email,
                    role=subject,
                    meet_url=analysis["meet_link"]
                )
            elif analysis["classification"] == "REJECTION":
                kanban_manager.update_job_status(matched_job_id, "Rejected")
                agent_logger.log_event("INBOX_AGENT", f"Autonomous transition: Job {matched_job_id} moved to 'Rejected'.")

        conn.close()
        return {
            "message_id": msg_id,
            "classification": analysis["classification"],
            "label": analysis["label"],
            "meet_link": analysis["meet_link"],
            "proposed_reply": analysis["proposed_reply"],
            "matched_job_id": matched_job_id
        }

    def get_all_messages(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Newest first; `status` narrows the read for callers that only act on one kind."""
        conn = get_db_connection()
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM inbox_messages WHERE status = ? ORDER BY id DESC", (status,))
        else:
            cursor.execute("SELECT * FROM inbox_messages ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def approve_and_send_reply(self, message_id: int, final_reply: str) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM inbox_messages WHERE id = ?", (message_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {"status": "ERROR", "message": "Message not found"}

        # Dispatch via SMTP helper
        res = email_finder.send_smtp_outreach(
            to_email=row["sender_email"],
            subject=f"Re: {row['subject']}",
            body_text=final_reply
        )

        if res.get("status") == "SENT":
            cursor.execute("UPDATE inbox_messages SET status = 'REPLIED' WHERE id = ?", (message_id,))
            conn.commit()
        conn.close()
        if res.get("status") == "SENT":
            agent_logger.log_event("INBOX_AGENT", "Reply sent through configured SMTP.")
            return {"status": "SUCCESS", "smtp_dispatch": res}
        agent_logger.log_event("INBOX_AGENT", f"Reply not sent ({res.get('status', 'FAILED')}).")
        return {"status": "FAILED", "smtp_dispatch": res}

inbox_agent = InboxAutomationAgent()
