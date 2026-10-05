"""
LinkedIn Session & Cookie Handshake Manager
Manages browser session persistence between Chrome Extension and Playwright Stealth Worker.
Exports & imports li_at and JSESSIONID cookies to eliminate login friction and 2FA prompts.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.app.core.config import settings
from backend.app.core.database import get_db_connection
from backend.app.core.event_logger import agent_logger
from backend.app.core.security import decrypt_secret, encrypt_secret
from backend.app.core.tenant import get_tenant_id

def _cookie_path():
    tenant_id = get_tenant_id()
    if tenant_id:
        safe_id = "".join(ch for ch in tenant_id if ch.isalnum())
        path = settings.DATA_PATH / "tenants" / safe_id / "browser_cookies.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return settings.DATA_PATH / "browser_cookies.json"

class LinkedInSessionManager:
    def __init__(self):
        pass

    @property
    def cookie_file(self):
        return _cookie_path()

    def get_status(self) -> Dict[str, Any]:
        """Returns the current state of stored LinkedIn credentials and Playwright session."""
        if not self.cookie_file.exists():
            return {
                "is_synced": False,
                "has_li_at": False,
                "cookie_count": 0,
                "last_synced_at": None,
                "message": "Henüz senkronize edilmiş LinkedIn oturumu bulunamadı. Eklentiden 'Handshake' yapınız."
            }

        try:
            with open(self.cookie_file, "r", encoding="utf-8") as f:
                cookies = json.loads(decrypt_secret(f.read()))

            if not isinstance(cookies, list):
                return {
                    "is_synced": False,
                    "has_li_at": False,
                    "cookie_count": 0,
                    "last_synced_at": None,
                    "message": "Geçersiz çerez formatı."
                }

            has_li_at = any(c.get("name") == "li_at" for c in cookies)
            has_jsession = any("JSESSIONID" in c.get("name", "") for c in cookies)
            
            # Check expiration of li_at
            li_at_cookie = next((c for c in cookies if c.get("name") == "li_at"), None)
            expires_at = None
            if li_at_cookie and li_at_cookie.get("expires"):
                exp_timestamp = li_at_cookie["expires"]
                if exp_timestamp > 0:
                    expires_at = datetime.fromtimestamp(exp_timestamp).strftime("%Y-%m-%d %H:%M:%S")

            # Fetch DB record
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM linkedin_sessions ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            conn.close()

            last_synced = row["last_synced_at"] if row else None

            return {
                "is_synced": True,
                "has_li_at": has_li_at,
                "has_jsessionid": has_jsession,
                "cookie_count": len(cookies),
                "expires_at": expires_at,
                "last_synced_at": last_synced,
                "message": "LinkedIn oturumu aktif ve Playwright stealth worker için hazır." if has_li_at else "Çerezler yüklendi fakat 'li_at' anahtarı eksik."
            }
        except Exception as e:
            return {
                "is_synced": False,
                "has_li_at": False,
                "cookie_count": 0,
                "last_synced_at": None,
                "message": f"Hata: {str(e)}"
            }

    def save_cookies(self, raw_cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Accepts raw cookie list from Chrome Extension or manual upload,
        formats them into standard Playwright cookie format, and saves them.
        """
        formatted_cookies = []
        for c in raw_cookies:
            if not isinstance(c, dict) or "name" not in c or "value" not in c:
                continue

            # Standardize Playwright cookie attributes
            domain = c.get("domain", ".linkedin.com")
            if not domain.startswith("."):
                domain = f".{domain}"

            cookie_obj = {
                "name": str(c["name"]),
                "value": str(c["value"]),
                "domain": domain,
                "path": c.get("path", "/"),
                "httpOnly": bool(c.get("httpOnly", False)),
                "secure": bool(c.get("secure", True)),
                "sameSite": c.get("sameSite", "Lax")
            }

            # Map expirationDate from Chrome format if present
            if "expirationDate" in c and c["expirationDate"]:
                cookie_obj["expires"] = int(c["expirationDate"])
            elif "expires" in c and c["expires"]:
                cookie_obj["expires"] = int(c["expires"])
            else:
                # Default 1 year expiry
                cookie_obj["expires"] = int(time.time()) + (365 * 24 * 3600)

            formatted_cookies.append(cookie_obj)

        # Write to JSON
        with open(self.cookie_file, "w", encoding="utf-8") as f:
            f.write(encrypt_secret(json.dumps(formatted_cookies, ensure_ascii=False)))

        has_li_at = any(c["name"] == "li_at" for c in formatted_cookies)
        
        # Record in DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO linkedin_sessions (
                is_synced, has_li_at, cookie_count, raw_cookie_preview, last_synced_at
            ) VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            1 if has_li_at else 0,
            len(formatted_cookies),
            f"Saved {len(formatted_cookies)} cookies. Has li_at: {has_li_at}"
        ))
        conn.commit()
        conn.close()

        agent_logger.log_event(
            "SESSION_HANDSHAKE",
            f"LinkedIn session synced successfully ({len(formatted_cookies)} cookies, li_at: {has_li_at})."
        )

        return {
            "status": "SUCCESS",
            "is_synced": True,
            "has_li_at": has_li_at,
            "cookie_count": len(formatted_cookies),
            "message": "LinkedIn oturumu başarıyla backend'e aktarıldı."
        }

    def clear_cookies(self) -> Dict[str, Any]:
        """Clears persisted LinkedIn session."""
        if self.cookie_file.exists():
            self.cookie_file.unlink()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM linkedin_sessions")
        conn.commit()
        conn.close()

        agent_logger.log_event("SESSION_HANDSHAKE", "LinkedIn session cookies cleared.")
        return {"status": "SUCCESS", "message": "Oturum çerezleri silindi."}

linkedin_session_manager = LinkedInSessionManager()
