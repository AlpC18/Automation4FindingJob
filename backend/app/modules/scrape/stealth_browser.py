"""
Playwright Stealth Browser & Autonomous Form Filler
Launches anti-detect headless/headful browser sessions, rotates user agents,
persists session cookies, and autonomously fills multi-step application forms.
"""

import logging
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import unquote, urlsplit
from backend.app.core.config import settings
from backend.app.core.security import decrypt_secret
from backend.app.core.tenant import get_tenant_id

logger = logging.getLogger(__name__)

def proxy_settings(proxy_url: str) -> Optional[Dict[str, str]]:
    """Turn RESIDENTIAL_PROXY_URL into Playwright's proxy option; None means no proxy is configured.

    A malformed URL raises instead of returning None: silently browsing from the
    user's own IP while they believe a proxy is active is the unsafe outcome.
    """
    if not (proxy_url or "").strip():
        return None
    parts = urlsplit(proxy_url.strip())
    if parts.scheme not in {"http", "https", "socks5"} or not parts.hostname:
        raise ValueError("RESIDENTIAL_PROXY_URL must look like http://user:pass@host:port")
    server = f"{parts.scheme}://{parts.hostname}" + (f":{parts.port}" if parts.port else "")
    proxy = {"server": server}
    if parts.username:
        proxy["username"] = unquote(parts.username)
        proxy["password"] = unquote(parts.password or "")
    return proxy


def _cookie_path():
    tenant_id = get_tenant_id()
    if tenant_id:
        safe_id = "".join(ch for ch in tenant_id if ch.isalnum())
        return settings.DATA_PATH / "tenants" / safe_id / "browser_cookies.json"
    return settings.DATA_PATH / "browser_cookies.json"

# Sandbox flags only: nothing here hides from the site that the browser is automated.
BROWSER_ARGS = ["--no-sandbox", "--disable-setuid-sandbox"]


class StealthBrowserWorker:
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ]

    @staticmethod
    def _linkedin_refusal(job_url: str) -> Optional[Dict[str, Any]]:
        """Why a LinkedIn session must not start right now; None when it may."""
        from backend.app.modules.scrape.rate_limiter import account_health
        base = {"url": job_url, "has_easy_apply": None, "applied": False, "submission_confirmed": False}
        if not settings.LINKEDIN_AUTOMATION_ENABLED:
            return {**base, "status": "DISABLED", "message": (
                "LinkedIn tarayıcı otomasyonu kapalı. LinkedIn otomatik erişimi yasaklar ve hesabın kısıtlanabilir; "
                "riski kabul ediyorsan .env dosyasında LINKEDIN_AUTOMATION_ENABLED=true yap."
            )}
        allowed, reason, _ = account_health.can_perform_action("linkedin", "apply")
        if not allowed:
            return {**base, "status": "QUOTA_EXHAUSTED", "message": reason}
        account_health.log_action("linkedin", "apply", "STARTED", job_url)
        return None

    async def execute_easy_apply_flow(
        self,
        job_url: str,
        applicant_data: Dict[str, Any],
        headless: bool = True,
        submit: bool = False,
    ) -> Dict[str, Any]:
        """
        Runs autonomous Playwright session to inspect form fields and apply.
        Reports FAILED when the browser cannot be started.
        """
        if "linkedin.com" in (urlsplit(job_url).hostname or ""):
            refusal = self._linkedin_refusal(job_url)
            if refusal:
                return refusal
        try:
            from playwright.async_api import async_playwright
            
            proxy = proxy_settings(settings.RESIDENTIAL_PROXY_URL)
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=headless,
                    **({"proxy": proxy} if proxy else {}),
                    args=BROWSER_ARGS
                )
                context = await browser.new_context(
                    user_agent=self.user_agents[0],
                    viewport={"width": 1280, "height": 800}
                )

                # Load stored session cookies if present
                cookie_path = _cookie_path()
                if cookie_path.exists():
                    try:
                        with open(cookie_path, "r") as f:
                            cookies = json.loads(decrypt_secret(f.read()))
                            await context.add_cookies(cookies)
                    except Exception:
                        logger.warning("Could not load saved browser cookies.", exc_info=True)

                page = await context.new_page()
                
                # Navigate
                await page.goto(job_url, timeout=20000, wait_until="domcontentloaded")
                
                # Extract page title
                title = await page.title()
                
                # Inspect the form. Submission is explicit and disabled by default.
                apply_button = await page.query_selector('button:has-text("Apply"), button:has-text("Easy Apply"), a:has-text("Apply")')
                has_easy_apply = apply_button is not None

                if submit and apply_button:
                    await apply_button.click()
                    await browser.close()
                    return {
                        "status": "SUBMIT_ATTEMPTED",
                        "url": job_url,
                        "page_title": title,
                        "has_easy_apply": has_easy_apply,
                        "applied": False,
                        "submission_confirmed": False,
                        "message": "Başvuru formu açıldı; gerçek gönderim doğrulanmadan başarılı sayılmadı.",
                    }

                await browser.close()

                return {
                    "status": "INSPECTED",
                    "url": job_url,
                    "page_title": title,
                    "has_easy_apply": has_easy_apply,
                    "applied": False,
                    "submission_confirmed": False,
                    "message": "Playwright oturumu açıldı ve ilan incelendi; başvuru gönderilmedi."
                }
        except Exception as e:
            # The page was never inspected, so nothing is known about its apply button.
            return {
                "status": "FAILED",
                "url": job_url,
                "has_easy_apply": None,
                "applied": False,
                "submission_confirmed": False,
                "simulation_reason": str(e)[:120],
                "message": "Tarayıcı oturumu açılamadı; ilan incelenmedi ve başvuru gönderilmedi."
            }

stealth_worker = StealthBrowserWorker()
