"""
Incoming Email AI Response Classifier & Interview Detector
Analyzes inbound recruiter emails and automatically updates pipeline states:
- Categorizes emails: INTERVIEW_INVITATION, TECHNICAL_ASSESSMENT, OFFER, REJECTION, GENERAL_UPDATE
- Extracts interview dates, calendar links, and interviewer contact details
- Automatically transitions job status in seen_jobs_tracker
- Broadcasts real-time WebSocket event to move Kanban cards dynamically
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.app.core.event_logger import agent_logger
from backend.app.core.llm_client import llm_client
from backend.app.core.ws_manager import ws_manager
from backend.app.modules.scrape.seen_jobs_tracker import seen_jobs_tracker


class InboxAIClassifier:
    """Classifies recruiter email responses and automates pipeline progression."""

    async def classify_and_process_email(
        self,
        sender_email: str,
        subject: str,
        body: str,
        associated_company: Optional[str] = None
    ) -> Dict[str, Any]:
        """Classifies incoming message and triggers automated pipeline status updates."""
        prompt = f"""
Incoming Recruiter Email:
From: {sender_email}
Subject: {subject}
Body:
{body[:2500]}

Classify this email into ONE of the following categories:
- INTERVIEW_INVITATION (recruiter wants to schedule an interview or sent a calendar link)
- TECHNICAL_ASSESSMENT (take-home test, HackerRank/LeetCode link)
- OFFER_RECEIVED (formal or verbal job offer extended)
- REJECTION (candidate was not selected, position filled)
- GENERAL_UPDATE (application received, confirmation, or generic check-in)

Return JSON with keys:
1. "category": The exact category string from above.
2. "confidence": Confidence score between 0.0 and 1.0.
3. "summary": A 1-sentence Turkish summary of what the recruiter is requesting or saying.
4. "action_needed": Boolean flag indicating whether user needs to reply or take action.
5. "detected_meeting_link": Any Zoom/Google Meet/Calendly URL found, or null.
6. "suggested_next_step": Recommended immediate action for the candidate.
"""
        res = await llm_client.generate_json(
            system_prompt="You are an expert HR Communications & Recruitment Email Parser.",
            user_prompt=prompt
        )

        category = res.get("category", "GENERAL_UPDATE") if res else "GENERAL_UPDATE"
        # No model answer (or none for this field) means no confidence, not a made-up high one.
        confidence = (res.get("confidence") or 0.0) if res else 0.0
        meeting_link = res.get("detected_meeting_link") or self._extract_url(body)

        # Automatic Pipeline Stage Progression
        matched_job_key = None
        new_status = None

        if associated_company:
            all_jobs = seen_jobs_tracker.get_all()
            for key, job in all_jobs.items():
                if associated_company.lower() in job.get("company", "").lower():
                    matched_job_key = key
                    break

        if matched_job_key:
            if category == "INTERVIEW_INVITATION":
                new_status = "interview"
                seen_jobs_tracker.mark_status(matched_job_key, "interview", notes=f"Auto-promoted by Inbox AI: {res.get('summary', '')}")
            elif category == "REJECTION":
                new_status = "rejected"
                seen_jobs_tracker.mark_status(matched_job_key, "rejected", notes="Recruiter rejection email received")
            elif category == "OFFER_RECEIVED":
                new_status = "offer"
                seen_jobs_tracker.mark_status(matched_job_key, "offer", notes="Offer letter / verbal offer received!")

            # Broadcast real-time event to automatically move Kanban board!
            if new_status:
                await ws_manager.broadcast("kanban_auto_move", {
                    "job_key": matched_job_key,
                    "new_status": new_status,
                    "company": associated_company,
                    "reason": category
                })

        agent_logger.log_event("INBOX_AI", f"Email from '{sender_email}' classified as {category} (Job Key: {matched_job_key})")

        return {
            "category": category,
            "confidence": confidence,
            "summary": res.get("summary", "E-posta işlendi.") if res else "E-posta sınıflandırıldı.",
            "action_needed": res.get("action_needed", False) if res else False,
            "meeting_link": meeting_link,
            "suggested_next_step": res.get("suggested_next_step", "Gelen kutusunu kontrol edin.") if res else "",
            "matched_job_key": matched_job_key,
            "pipeline_updated_to": new_status
        }

    def _extract_url(self, text: str) -> Optional[str]:
        """Extracts Zoom, Meet, or Calendly links from raw text."""
        match = re.search(r"https?://(meet\.google\.com|[\w-]+\.zoom\.us|calendly\.com)/[^\s]+", text)
        return match.group(0) if match else None


inbox_ai_classifier = InboxAIClassifier()
