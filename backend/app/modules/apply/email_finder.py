"""Unverified business-email pattern suggestions and real SMTP delivery."""

import logging
import re
from typing import Any, Dict, Optional

from backend.app.core.config import settings
from backend.app.core.security_email import is_configured, send_security_email

logger = logging.getLogger(__name__)


class DecisionMakerEmailFinder:
    def infer_company_domain(self, company_name: str) -> str:
        """Return a domain guess only; this does not resolve or verify a company domain."""
        clean = re.sub(r"[^a-zA-Z0-9]", "", company_name.lower())
        return f"{clean}.com" if clean else ""

    def send_smtp_outreach(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        sender_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send only through configured SMTP; never report simulated delivery."""
        recipient = (to_email or "").strip()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", recipient):
            return {"status": "INVALID_RECIPIENT", "message": "Geçerli bir e-posta adresi gerekli; e-posta gönderilmedi."}
        if not is_configured():
            return {"status": "NOT_CONFIGURED", "message": "SMTP yapılandırılmamış; e-posta gönderilmedi."}

        configured_sender = settings.SMTP_FROM_EMAIL.strip() or settings.SMTP_USER.strip()
        if sender_email and sender_email.strip().lower() != configured_sender.lower():
            return {"status": "INVALID_SENDER", "message": "Gönderici adresi SMTP ayarlarıyla eşleşmiyor; e-posta gönderilmedi."}

        try:
            send_security_email(recipient, subject, body_text)
        except Exception as exc:
            # SMTP exception strings can contain host/account details; keep those out of
            # both API responses and logs while retaining a useful failure category.
            logger.error("SMTP outreach failed (%s)", type(exc).__name__)
            return {"status": "FAILED", "message": "E-posta gönderilemedi. SMTP ayarlarını ve sunucu kayıtlarını kontrol edin."}
        return {"status": "SENT", "message": "E-posta SMTP sunucusuna gönderildi.", "recipient": recipient}


email_finder = DecisionMakerEmailFinder()
