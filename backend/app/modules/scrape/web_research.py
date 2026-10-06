"""
Web Research Escalation Engine
Adapted from MadsLorentzen/ai-job-search 09-web-research.md concept.

Implements a multi-step fallback chain for fetching job postings and company pages:

1. Direct fetch (standard UA) → if 403...
2. Check robots.txt permission → if allowed...
3. Retry with browser-like headers → if still fails...
4. Try Google Cache or web archive → if still fails...
5. Web search for the page content as last resort

This replaces the naive "fetch or fail" approach with a resilient chain
that respects site policies while maximizing data retrieval.
"""

import re
import subprocess
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlsplit, quote

from backend.app.tools.robots_check import check_robots_permission
from backend.app.core.event_logger import agent_logger

BROWSER_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
)

BOT_UA = 'CareerAgent-Bot/1.0'


MAX_REDIRECTS = 5


def _curl_once(url: str, user_agent: str, timeout: int) -> Tuple[str, int, str]:
    """One request, redirects not followed. Returns (body, http_code, redirect_url)."""
    try:
        result = subprocess.run(
            [
                'curl', '-sS',
                '--proto', '=http,https',
                '--max-time', str(timeout),
                '-A', user_agent,
                '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                '-H', 'Accept-Language: en-US,en;q=0.9,tr;q=0.8',
                '-o', '-',
                '-w', '\n%{http_code} %{redirect_url}',
                '--', url
            ],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        body, _, trailer = result.stdout.rpartition('\n')
        code_str, _, redirect_url = trailer.partition(' ')
        try:
            return body, int(code_str.strip()), redirect_url.strip()
        except ValueError:
            return result.stdout, 0, ""
    except Exception as e:
        agent_logger.log_event("WEB_RESEARCH", f"curl failed for {url}: {e}")
        return "", 0, ""


def _curl_fetch(url: str, user_agent: str, timeout: int = 15) -> Tuple[str, int]:
    """Fetch a URL with curl. Returns (body, http_code)."""
    # Redirects are followed here, not by curl, so each hop gets the public-address check.
    # ponytail: the check resolves DNS separately from curl; pin the resolved IP with --resolve if rebinding matters.
    from backend.app.modules.scrape.job_link_health import _public_http_url
    for _ in range(MAX_REDIRECTS + 1):
        body, code, redirect_url = _curl_once(url, user_agent, timeout)
        if not (300 <= code < 400 and redirect_url):
            return body, code
        allowed, reason = _public_http_url(redirect_url)
        if not allowed:
            agent_logger.log_event("WEB_RESEARCH", f"Redirect from {url} refused: {reason}")
            return "", 0
        url = redirect_url
    return "", 0


def _extract_text_from_html(html: str) -> str:
    """Basic HTML to text extraction."""
    # Remove script and style elements
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.S | re.I)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.S | re.I)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Decode common entities
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


class WebResearchEngine:
    """Multi-step web research with escalation fallback."""

    def fetch_with_escalation(
        self,
        url: str,
        context: str = "job_posting",
    ) -> Dict[str, Any]:
        """
        Fetch a URL using the escalation chain.

        Args:
            url: The URL to fetch
            context: What we're fetching ("job_posting", "company_page", etc.)

        Returns:
            Dict with 'success', 'content', 'method', 'url', 'error'
        """
        # The URL comes from the user: refuse local and private-network addresses before any request is made.
        from backend.app.modules.scrape.job_link_health import _public_http_url
        allowed, reason = _public_http_url(url)
        if not allowed:
            return {"success": False, "content": "", "method": "blocked", "url": url, "error": reason}

        agent_logger.log_event(
            "WEB_RESEARCH",
            f"Starting escalation fetch for {context}: {url}"
        )

        # Step 1: Direct fetch with bot UA
        body, code = _curl_fetch(url, BOT_UA)
        if code == 200 and len(body) > 200:
            text = _extract_text_from_html(body)
            if len(text) > 100:
                agent_logger.log_event("WEB_RESEARCH", f"Step 1 success (direct fetch): {url}")
                return {
                    "success": True,
                    "content": text,
                    "html": body,
                    "method": "direct_fetch",
                    "url": url,
                    "http_code": code,
                }

        if code == 403:
            agent_logger.log_event("WEB_RESEARCH", f"Step 1 got 403 for {url}, checking robots.txt...")

            # Step 2: Check robots.txt permission
            robots_allowed, robots_reason = check_robots_permission(url)

            if robots_allowed:
                # Step 3: Retry with browser-like headers
                agent_logger.log_event("WEB_RESEARCH", f"Robots.txt allows, retrying with browser UA: {url}")
                body, code = _curl_fetch(url, BROWSER_UA)
                if code == 200 and len(body) > 200:
                    text = _extract_text_from_html(body)
                    if len(text) > 100:
                        agent_logger.log_event("WEB_RESEARCH", f"Step 3 success (browser UA): {url}")
                        return {
                            "success": True,
                            "content": text,
                            "html": body,
                            "method": "browser_ua_retry",
                            "url": url,
                            "http_code": code,
                        }
            else:
                agent_logger.log_event(
                    "WEB_RESEARCH",
                    f"Robots.txt disallows: {robots_reason}. Skipping browser retry."
                )

        # Step 4: Try Google Cache
        cache_result = self._try_google_cache(url)
        if cache_result:
            agent_logger.log_event("WEB_RESEARCH", f"Step 4 success (Google cache): {url}")
            return cache_result

        # Step 5: Try web.archive.org (Wayback Machine)
        archive_result = self._try_wayback(url)
        if archive_result:
            agent_logger.log_event("WEB_RESEARCH", f"Step 5 success (Wayback Machine): {url}")
            return archive_result

        # All steps failed
        agent_logger.log_event(
            "WEB_RESEARCH",
            f"All escalation steps failed for {url} (last HTTP code: {code})"
        )
        return {
            "success": False,
            "content": "",
            "method": "all_failed",
            "url": url,
            "http_code": code,
            "error": f"Could not fetch {url} after full escalation chain",
        }

    def _try_google_cache(self, url: str) -> Optional[Dict[str, Any]]:
        """Try fetching from Google's cache."""
        cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}"
        body, code = _curl_fetch(cache_url, BROWSER_UA, timeout=10)
        if code == 200 and len(body) > 200:
            text = _extract_text_from_html(body)
            if len(text) > 100:
                return {
                    "success": True,
                    "content": text,
                    "html": body,
                    "method": "google_cache",
                    "url": url,
                    "http_code": code,
                    "note": "Content from Google Cache — may not be the latest version",
                }
        return None

    def _try_wayback(self, url: str) -> Optional[Dict[str, Any]]:
        """Try fetching from the Wayback Machine."""
        # Check if a snapshot exists
        api_url = f"https://archive.org/wayback/available?url={quote(url, safe='')}"
        body, code = _curl_fetch(api_url, BOT_UA, timeout=10)

        if code == 200 and "closest" in body:
            try:
                import json
                data = json.loads(body)
                snapshot = data.get("archived_snapshots", {}).get("closest", {})
                if snapshot.get("available") and snapshot.get("url"):
                    snap_url = snapshot["url"]
                    snap_body, snap_code = _curl_fetch(snap_url, BOT_UA, timeout=15)
                    if snap_code == 200 and len(snap_body) > 200:
                        text = _extract_text_from_html(snap_body)
                        if len(text) > 100:
                            return {
                                "success": True,
                                "content": text,
                                "html": snap_body,
                                "method": "wayback_machine",
                                "url": url,
                                "snapshot_url": snap_url,
                                "snapshot_timestamp": snapshot.get("timestamp"),
                                "http_code": snap_code,
                                "note": "Content from Wayback Machine — may be outdated",
                            }
            except (json.JSONDecodeError, KeyError):
                pass
        return None

    def research_company(
        self,
        company_name: str,
        company_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Research a company using multiple web sources.

        Returns structured company info for use in applications.
        """
        research = {
            "company_name": company_name,
            "sources": [],
        }

        # 1. Try company website
        if company_url:
            result = self.fetch_with_escalation(company_url, "company_page")
            if result["success"]:
                research["website_content"] = result["content"][:3000]
                research["sources"].append({
                    "type": "website",
                    "url": company_url,
                    "method": result["method"],
                })

        # 2. Try LinkedIn company page
        linkedin_url = f"https://www.linkedin.com/company/{company_name.lower().replace(' ', '-')}/"
        li_result = self.fetch_with_escalation(linkedin_url, "linkedin_company")
        if li_result["success"]:
            research["linkedin_content"] = li_result["content"][:2000]
            research["sources"].append({
                "type": "linkedin",
                "url": linkedin_url,
                "method": li_result["method"],
            })

        return research


# Module-level singleton
web_research_engine = WebResearchEngine()
