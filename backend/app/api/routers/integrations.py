"""Inbound employer email classification and outbound channel webhooks."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.modules.outcome.inbox_ai_classifier import inbox_ai_classifier
from backend.app.modules.outcome.webhook_hub import webhook_hub

router = APIRouter()


class ClassifyEmailRequest(BaseModel):
    sender_email: str
    subject: str
    body: str
    associated_company: Optional[str] = None


@router.post("/inbox/classify_email")
async def classify_incoming_email(req: ClassifyEmailRequest):
    return await inbox_ai_classifier.classify_and_process_email(
        sender_email=req.sender_email,
        subject=req.subject,
        body=req.body,
        associated_company=req.associated_company,
    )


class SlackAlertRequest(BaseModel):
    webhook_url: str
    title: str
    message: str
    company: Optional[str] = None
    score: Optional[float] = None
    action_url: Optional[str] = None


@router.post("/webhook/slack")
async def send_slack_webhook(req: SlackAlertRequest):
    return await webhook_hub.send_slack_alert(
        webhook_url=req.webhook_url,
        title=req.title,
        message=req.message,
        company=req.company,
        score=req.score,
        action_url=req.action_url,
    )


class DiscordAlertRequest(BaseModel):
    webhook_url: str
    title: str
    message: str
    company: Optional[str] = None
    score: Optional[float] = None


@router.post("/webhook/discord")
async def send_discord_webhook(req: DiscordAlertRequest):
    return await webhook_hub.send_discord_alert(
        webhook_url=req.webhook_url,
        title=req.title,
        message=req.message,
        company=req.company,
        score=req.score,
    )
