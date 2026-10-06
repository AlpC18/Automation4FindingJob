"""
Multi-Channel Webhook Dispatcher Hub (Slack & Discord)
Sends formatted cards and instant alerts to team channels:
- Slack Incoming Webhook (Blocks & formatted attachments)
- Discord Webhook (Rich embeds with color badges)
- Event triggers: High Match Job Found, Auto-Apply Approval Required, Interview Booked
"""

import json
import urllib.request
from typing import Dict, Any, List, Optional
from backend.app.core.event_logger import agent_logger


# The address is typed in by the user; without this check the server could be pointed at
# local files or services on the private network.
from backend.app.modules.scrape.job_link_health import _public_http_url


class WebhookHub:
    """Dispatches event cards to Slack and Discord endpoints."""

    def __init__(self):
        pass

    async def send_slack_alert(
        self,
        webhook_url: str,
        title: str,
        message: str,
        company: Optional[str] = None,
        score: Optional[float] = None,
        action_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sends rich Slack block kit card to a channel webhook."""
        if not webhook_url:
            return {"success": False, "error": "Slack webhook URL not provided."}
        allowed, reason = _public_http_url(webhook_url)
        if not allowed:
            return {"success": False, "error": reason}

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🚀 {title}", "emoji": True}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Şirket:*\n{company or 'Belirtilmedi'}"},
                    {"type": "mrkdwn", "text": f"*ATS Eşleşme:*\n%{score:.0f}" if score else "*Durum:*\nAksiyon Gerekli"}
                ]
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message}
            }
        ]

        if action_url:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "İlanı İncele & Onayla"},
                        "url": action_url,
                        "style": "primary"
                    }
                ]
            })

        payload = json.dumps({"blocks": blocks}).encode("utf-8")
        try:
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
            agent_logger.log_event("WEBHOOK", f"Slack alert sent successfully (status: {status})")
            return {"success": True, "status_code": status}
        except Exception as e:
            agent_logger.log_event("WEBHOOK", f"Slack alert failed: {e}")
            return {"success": False, "error": str(e)}

    async def send_discord_alert(
        self,
        webhook_url: str,
        title: str,
        message: str,
        company: Optional[str] = None,
        score: Optional[float] = None
    ) -> Dict[str, Any]:
        """Sends rich Discord embed message."""
        if not webhook_url:
            return {"success": False, "error": "Discord webhook URL not provided."}
        allowed, reason = _public_http_url(webhook_url)
        if not allowed:
            return {"success": False, "error": reason}

        embed = {
            "title": f"🎯 {title}",
            "description": message,
            "color": 3447003, # Blue hex
            "fields": []
        }

        if company:
            embed["fields"].append({"name": "Şirket", "value": company, "inline": True})
        if score:
            embed["fields"].append({"name": "ATS Skoru", "value": f"%{score:.0f}", "inline": True})

        payload = json.dumps({"embeds": [embed]}).encode("utf-8")
        try:
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
            agent_logger.log_event("WEBHOOK", f"Discord alert sent successfully (status: {status})")
            return {"success": True, "status_code": status}
        except Exception as e:
            agent_logger.log_event("WEBHOOK", f"Discord alert failed: {e}")
            return {"success": False, "error": str(e)}


webhook_hub = WebhookHub()
