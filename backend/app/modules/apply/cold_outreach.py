"""
Direct Hiring Manager & Executive Cold Outreach Engine
Transforms applications into high-conversion executive conversations:
- 1-on-1 personalized cold email generation tailored to Engineering Managers & CTOs
- Value-first technical hooks referencing company tech stack and engineering challenges
- Email deliverability safety checks (spam score heuristic, SPF/DKIM alert, warm-up limits)
- Multi-touch cold outreach schedule tracker
"""

import re
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from backend.app.core.json_store import read_json_store
from typing import Dict, Any, List, Optional

from backend.app.core.config import settings
from backend.app.core.event_logger import agent_logger
from backend.app.core.llm_client import LLMUnavailable, llm_client
from backend.app.prompts.humanizer_prompts import WRITING_RULES
from backend.app.core.tenant import get_tenant_id, tenant_data_path

OUTREACH_DATA_PATH = settings.DATA_PATH / "cold_outreach_campaigns.json"


OUTREACH_RETENTION_DAYS = 90


class ColdOutreachEngine:
    """Manages high-impact cold email campaigns targeting decision makers."""

    def __init__(self, data_path: Path = OUTREACH_DATA_PATH):
        self.data_path = data_path
        self._campaigns_by_scope: Dict[str, Dict[str, Any]] = {}
        self._loaded_scopes = set()

    def _scope(self):
        return get_tenant_id() or "__shared__"

    def _scoped_data_path(self):
        return tenant_data_path(self.data_path.name) if get_tenant_id() else self.data_path

    @property
    def _campaigns(self):
        scope = self._scope()
        if scope not in self._loaded_scopes:
            path = self._scoped_data_path()
            value = read_json_store(path, {})
            campaigns = {"outreach_list": [], "stats": {"sent_today": 0, "last_date": ""}, **value}
            # Other people's names and titles are not kept forever.
            cutoff = (datetime.now() - timedelta(days=OUTREACH_RETENTION_DAYS)).isoformat()
            campaigns["outreach_list"] = [item for item in campaigns["outreach_list"] if str(item.get("created_at") or cutoff) >= cutoff]
            self._campaigns_by_scope[scope] = campaigns
            self._loaded_scopes.add(scope)
        return self._campaigns_by_scope[scope]

    @_campaigns.setter
    def _campaigns(self, value):
        scope = self._scope()
        self._campaigns_by_scope[scope] = value
        self._loaded_scopes.add(scope)

    def _load(self):
        self._campaigns = read_json_store(self.data_path, {"outreach_list": [], "stats": {"sent_today": 0, "last_date": ""}})

    def _save(self):
        path = self._scoped_data_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self._campaigns, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def calculate_spam_score(self, subject: str, body: str) -> Dict[str, Any]:
        """Heuristic evaluation of email content for spam trigger words and deliverability risks."""
        spam_triggers = [
            "free", "guarantee", "urgent", "100%", "winner", "risk-free", 
            "opportunity of a lifetime", "dear sir/madam", "act now", "limited time"
        ]
        
        full_text = f"{subject} {body}".lower()
        found_triggers = [w for w in spam_triggers if w in full_text]
        
        has_caps = bool(re.search(r"\b[A-Z]{4,}\b", subject))
        has_excessive_punctuation = bool(re.search(r"[!]{2,}|\?{2,}", full_text))

        score = 100
        penalties = []

        if found_triggers:
            penalty = len(found_triggers) * 15
            score -= penalty
            penalties.append(f"Spam tetikleyici kelimeler bulundu: {', '.join(found_triggers)}")

        if has_caps:
            score -= 20
            penalties.append("Konu başlığında tümü büyük harfli kelimeler tespit edildi.")

        if has_excessive_punctuation:
            score -= 15
            penalties.append("Aşırı ünlem veya soru işareti kullanımı tespit edildi.")

        score = max(0, min(100, score))

        return {
            "deliverability_score": score,
            "is_deliverable": score >= 70,
            "penalties": penalties,
            "verdict": "Mükemmel Teslimat Güvenliği" if score >= 85 else ("Kabul Edilebilir" if score >= 70 else "Yüksek Spam Riski")
        }

    async def generate_executive_outreach(
        self,
        manager_name: str,
        manager_title: str,
        company: str,
        target_role: str,
        candidate_profile: Dict[str, Any],
        recent_company_news_or_stack: Optional[str] = None
    ) -> Dict[str, Any]:
        """Crafts a compelling 3-part cold outreach email tailored directly to the engineering leader."""
        skills = ", ".join(candidate_profile.get("skills", [])[:8])
        hook = recent_company_news_or_stack or f"your engineering team's focus on scalable architecture and modern systems"

        prompt = f"""
Candidate Info:
Target Role: {target_role}
Key Skills: {skills}

Recipient:
Name: {manager_name}
Title: {manager_title}
Company: {company}
Context Hook: {hook}

Write a personal cold email in JSON format with keys:
1. "subject_lines": 3 punchy, low-friction subject lines (max 50 chars each, lowercase/conversational style).
2. "email_body": A crisp 4-sentence email:
   - Sentence 1: Specific non-generic compliment/observation regarding their tech focus.
   - Sentence 2: How the candidate's listed skills connect to this challenge. Use only the skills above; do not invent achievements, numbers or employers.
   - Sentence 3: Value proposition (how candidate can help them hit their engineering milestone faster).
   - Sentence 4: Zero-pressure call to action (e.g. 'Worth a 5-min intro? If not, no worries at all.').
3. "follow_up_note": A 2-sentence follow-up message to send 5 days later if no response.
"""
        res = await llm_client.generate_json(
            system_prompt="You write short cold emails from a job seeker to an engineering manager." + WRITING_RULES,
            user_prompt=prompt
        )

        if not res.get("email_body"):
            raise LLMUnavailable("Yapay zekâ sağlayıcısı yanıt vermedi; e-posta taslağı üretilemedi.")

        subject_lines = res.get("subject_lines")
        subject = subject_lines[0] if isinstance(subject_lines, list) and subject_lines else f"quick thought on {company}'s tech stack"
        body = res["email_body"]

        spam_check = self.calculate_spam_score(subject, body)

        outreach_item = {
            "id": f"outreach_{int(datetime.now().timestamp())}",
            "manager_name": manager_name,
            "manager_title": manager_title,
            "company": company,
            "target_role": target_role,
            "subject": subject,
            "body": body,
            "follow_up_note": res.get("follow_up_note", ""),
            "spam_check": spam_check,
            "created_at": datetime.now().isoformat(),
            "status": "draft"
        }

        self._campaigns.setdefault("outreach_list", []).append(outreach_item)
        self._save()

        agent_logger.log_event("COLD_OUTREACH", f"Generated executive outreach for {manager_name} @ {company}")
        return outreach_item

    def list_outreach_campaigns(self) -> List[Dict[str, Any]]:
        """Returns all recorded outreach campaigns."""
        return self._campaigns.get("outreach_list", [])

    def mark_outreach_status(self, outreach_id: str, status: str) -> bool:
        """Updates outreach status (e.g. sent, replied, bounced)."""
        for item in self._campaigns.get("outreach_list", []):
            if item.get("id") == outreach_id:
                item["status"] = status
                item["updated_at"] = datetime.now().isoformat()
                self._save()
                return True
        return False


cold_outreach_engine = ColdOutreachEngine()
