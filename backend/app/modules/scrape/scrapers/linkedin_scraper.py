"""LinkedIn job scraper with resilient dual-engine: Apify Actor + Public Guest Feed."""

import re
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, List
from bs4 import BeautifulSoup

from backend.app.core.event_logger import agent_logger
from backend.app.modules.scrape.live_sources import apify_job_source
from backend.app.modules.scrape.source_registry import get_source_config


class LinkedInScraper:
    def __init__(self):
        self.platform_name = "linkedin"

    def fetch_jobs(self, query: str = "Software Engineer", location: str = None) -> List[Dict[str, Any]]:
        # 1. Try Apify if user configured an Actor and token
        source_config = get_source_config("linkedin")
        if source_config.get("has_custom_config") and source_config.get("enabled"):
            try:
                jobs = apify_job_source.fetch("linkedin", query, location)
                if jobs:
                    return jobs
            except Exception as exc:
                agent_logger.log_event("LINKEDIN_SCRAPER", f"Apify search failed ({exc}), falling back to public feed.")

        # 2. Resilient Public Guest Feed (Zero-token, always works)
        return self._fetch_public_feed(query=query, location=location)

    def _fetch_public_feed(self, query: str, location: str = None, limit: int = 25) -> List[Dict[str, Any]]:
        params = {
            "keywords": query or "Software Engineer",
            "location": location or "",
            "start": 0,
        }
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        jobs: List[Dict[str, Any]] = []
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            cards = soup.find_all("li")
            for card in cards:
                title_el = card.find("h3", class_="base-search-card__title")
                company_el = card.find("h4", class_="base-search-card__subtitle")
                loc_el = card.find("span", class_="job-search-card__location")
                link_el = card.find("a", class_="base-card__full-link")
                time_el = card.find("time")

                title = title_el.get_text(strip=True) if title_el else ""
                company = company_el.get_text(strip=True) if company_el else ""
                loc = loc_el.get_text(strip=True) if loc_el else ""
                raw_link = link_el.get("href", "") if link_el else ""
                clean_link = raw_link.split("?")[0] if raw_link else ""
                posted = time_el.get_text(strip=True) if time_el else ""

                if not title or not clean_link:
                    continue

                match = re.search(r"-(\d+)(?:\?|$)", clean_link) or re.search(r"view/(\d+)", clean_link)
                job_num = match.group(1) if match else uuid.uuid4().hex[:8]
                job_id = f"li-{job_num}"

                is_remote = "remote" in (title + loc).lower()
                remote_type = "Remote" if is_remote else "On-site"

                jobs.append({
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "location": loc or (location or "Remote"),
                    "remote_type": remote_type,
                    "platform": "linkedin",
                    "url": clean_link,
                    "description": f"{title} at {company}. Location: {loc or 'Remote'}. Posted: {posted or 'Recently'}. Click the direct job link to view full details and apply on LinkedIn.",
                    "posted_date": posted or "Recent",
                    "salary_range": "Not disclosed",
                })
                if len(jobs) >= limit:
                    break
        except Exception as exc:
            agent_logger.log_event("LINKEDIN_SCRAPER", f"Public LinkedIn search failed: {exc}")
        return jobs
