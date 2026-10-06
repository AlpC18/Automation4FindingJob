"""
Notion Sync Module
Adapted from MadsLorentzen/ai-job-search notion-sync command.

Syncs job search data to a Notion database for visual tracking:
- Creates/updates pages for each tracked job
- Maps status to Notion select properties
- Syncs scores, deadlines, and notes
- Bidirectional: reads Notion status updates back

Requires: NOTION_API_KEY and NOTION_DATABASE_ID in environment.
"""

import logging
import json
import os

import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.app.core.event_logger import agent_logger

logger = logging.getLogger(__name__)

NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")
NOTION_API_URL = "https://api.notion.com/v1"


class NotionSync:
    """Syncs job tracking data with a Notion database."""

    def __init__(self):
        self.api_key = NOTION_API_KEY
        self.database_id = NOTION_DATABASE_ID

    def is_configured(self) -> bool:
        return bool(self.api_key and self.database_id)

    def get_status(self) -> Dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "has_api_key": bool(self.api_key),
            "has_database_id": bool(self.database_id),
            "database_id": self.database_id[:8] + "..." if self.database_id else "",
        }

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

    def sync_job(
        self,
        job_data: Dict[str, Any],
        notion_page_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Sync a single job to Notion (create or update).
        """
        if not self.is_configured():
            return {"error": "Notion is not configured. Set NOTION_API_KEY and NOTION_DATABASE_ID."}

        properties = self._build_properties(job_data)

        try:
            # Sent in a header by httpx: on a curl command line the key was readable by other local processes.
            with httpx.Client(timeout=15) as client:
                if notion_page_id:
                    reply = client.patch(f"{NOTION_API_URL}/pages/{notion_page_id}", headers=self._headers(), json={"properties": properties})
                    action = "updated"
                else:
                    reply = client.post(
                        f"{NOTION_API_URL}/pages", headers=self._headers(),
                        json={"parent": {"database_id": self.database_id}, "properties": properties},
                    )
                    action = "created"
            response = reply.json()

            if "id" in response:
                agent_logger.log_event(
                    "NOTION_SYNC",
                    f"Page {action}: {job_data.get('company')} — {job_data.get('title')}"
                )
                return {
                    "success": True,
                    "action": action,
                    "notion_page_id": response["id"],
                }
            else:
                return {
                    "success": False,
                    "error": response.get("message", "Unknown Notion API error"),
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def sync_batch(
        self,
        jobs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Sync multiple jobs to Notion."""
        if not self.is_configured():
            return {"error": "Notion is not configured."}

        results = {"created": 0, "updated": 0, "errors": 0}
        for job in jobs:
            result = self.sync_job(job, job.get("notion_page_id"))
            if result.get("success"):
                if result["action"] == "created":
                    results["created"] += 1
                else:
                    results["updated"] += 1
            else:
                results["errors"] += 1

        agent_logger.log_event(
            "NOTION_SYNC",
            f"Batch sync: {results['created']} created, "
            f"{results['updated']} updated, {results['errors']} errors"
        )
        return results

    def _build_properties(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build Notion page properties from job data."""
        props = {
            "Pozisyon": {
                "title": [{"text": {"content": job_data.get("title", "Untitled")}}]
            },
            "Şirket": {
                "rich_text": [{"text": {"content": job_data.get("company", "")}}]
            },
            "Durum": {
                "select": {"name": self._map_status(job_data.get("status", "new"))}
            },
        }

        score = job_data.get("match_score", job_data.get("score"))
        if score is not None:
            props["Skor"] = {"number": float(score)}

        url = job_data.get("url")
        if url:
            props["URL"] = {"url": url}

        location = job_data.get("location")
        if location:
            props["Lokasyon"] = {
                "rich_text": [{"text": {"content": location}}]
            }

        deadline = job_data.get("deadline")
        if deadline:
            try:
                props["Son Tarih"] = {"date": {"start": deadline}}
            except Exception:
                logger.warning("Could not set the deadline on the Notion page.", exc_info=True)

        return props

    def _map_status(self, status: str) -> str:
        """Map internal status to Notion select option."""
        status_map = {
            "new": "🆕 Yeni",
            "ranked": "📊 Değerlendirildi",
            "applied": "📨 Başvuruldu",
            "interview": "🎤 Mülakat",
            "hired": "✅ Kabul",
            "rejected": "❌ Reddedildi",
            "no_response": "⏳ Cevap Yok",
            "expired": "🕐 Süresi Geçti",
            "skipped": "⏭️ Atlandı",
        }
        return status_map.get(status, status)


# Module-level singleton
notion_sync = NotionSync()
