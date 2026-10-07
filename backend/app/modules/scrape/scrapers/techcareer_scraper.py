"""Techcareer.net source (technology jobs in Türkiye): reads the public job pages, no API key.

robots.txt allows /jobs. The site embeds its data as JSON in each page, so nothing is
guessed from markup. Requests are sequential, rate limited and capped per scan.
"""

import json
import re
import time
from typing import Any, Dict, List, Optional

import httpx

from backend.app.core.config import settings
from backend.app.modules.scrape.live_sources import normalize_job
from backend.app.modules.scrape.robots import robots_allows

JOBS_URL = "https://www.techcareer.net/jobs"
MAX_LIST_PAGES = 10
MAX_DETAIL_PAGES = 25
REQUEST_DELAY_SECONDS = 0.4
LISTING_CACHE_SECONDS = 600
WORKPLACE_LABELS = {"uzaktan": "Remote", "hibrit": "Hybrid", "iş yerinde": "Onsite"}
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_GENERIC_QUERY_WORDS = {"senior", "junior", "lead", "intern", "remote", "the", "and", "for"}


def page_props(page_html: str) -> Dict[str, Any]:
    """The page's embedded data; an empty dict when the site layout no longer matches."""
    match = _NEXT_DATA.search(page_html or "")
    try:
        props = json.loads(match.group(1))["props"]["pageProps"] if match else {}
    except (ValueError, KeyError, TypeError):
        return {}
    return props if isinstance(props, dict) else {}


def _workplace(labels: Any) -> Optional[str]:
    # str.lower() turns the Turkish capital "İ" into "i" plus a combining dot; drop the dot so labels compare equal.
    first = str(labels[0]).strip().lower().replace("\u0307", "") if isinstance(labels, list) and labels else ""
    return WORKPLACE_LABELS.get(first)


def parse_listing(page_html: str) -> Dict[str, Any]:
    """Open jobs on one list page plus the total page count."""
    listing = page_props(page_html).get("initialJobList") or {}
    jobs = []
    for item in listing.get("jobListItems") or []:
        if not isinstance(item, dict) or item.get("isDisabledJob") or not item.get("slug") or not item.get("title"):
            continue
        owner = item.get("owner") if isinstance(item.get("owner"), dict) else {}
        jobs.append({key: value for key, value in {
            "id": f"techcareer-{item.get('id')}",
            "title": item["title"],
            "title_en": item.get("jobTitleEn") or "",
            "company": owner.get("name") or item.get("hiddenCompanyInfo") or "",
            "url": f"{JOBS_URL}/detail/{item['slug']}",
            "location": item.get("location") or "Türkiye",
            "workplace_type": _workplace(item.get("workPlaces")),
        }.items() if value})
    pages = (listing.get("pagination") or {}).get("pageCount")
    return {"jobs": jobs, "page_count": int(pages) if str(pages).isdigit() else 1}


def parse_detail(page_html: str) -> Dict[str, Any]:
    """Description, skills, posting date and application deadline from a job page."""
    detail = page_props(page_html).get("jobDetail") or {}
    head = detail.get("head") if isinstance(detail.get("head"), dict) else {}
    content = detail.get("content") if isinstance(detail.get("content"), dict) else {}
    return {key: value for key, value in {
        "description": content.get("description"),
        "tags": [str(skill) for skill in content.get("skills") or [] if skill],
        "date": head.get("startDate"),
        "deadline": head.get("endDate"),
    }.items() if value}


def matches_query(job: Dict[str, Any], query: str) -> bool:
    """Titles are all the list shows, so any meaningful query word in either language is a match."""
    words = [word for word in re.findall(r"[\w+#.]+", (query or "").casefold()) if len(word) > 2 and word not in _GENERIC_QUERY_WORDS]
    haystack = f"{job.get('title', '')} {job.get('title_en', '')}".casefold()
    return not words or any(word in haystack for word in words)


class TechcareerScraper:
    def __init__(self):
        self.platform_name = "techcareer"
        # One scan asks once per target role; the site has a single small list, so read it once.
        self._cards: List[Dict[str, Any]] = []
        self._cards_read_at = 0.0
        self._details: Dict[str, Dict[str, Any]] = {}

    def fetch_jobs(self, query: str = "Software Engineer", location: str = None) -> List[Dict[str, Any]]:
        headers = {"User-Agent": settings.JOB_SOURCE_USER_AGENT, "Accept": "text/html"}
        location_key = (location or "").strip().casefold()
        if not robots_allows(JOBS_URL):
            raise RuntimeError("techcareer: the site's robots.txt does not allow reading the job list")
        with httpx.Client(timeout=settings.JOB_SOURCE_TIMEOUT_SECONDS, headers=headers, follow_redirects=True) as client:
            if time.monotonic() - self._cards_read_at > LISTING_CACHE_SECONDS:
                self._cards, self._details = [], {}
            cards = self._cards
            page, page_count = 1, 1
            while not cards and page <= min(page_count, MAX_LIST_PAGES):
                if page > 1:
                    time.sleep(REQUEST_DELAY_SECONDS)
                response = client.get(JOBS_URL, params={"jobs[page]": page})
                response.raise_for_status()
                listing = parse_listing(response.text)
                if page == 1 and not listing["jobs"]:
                    raise RuntimeError("techcareer: no jobs found on the list page; the site layout may have changed")
                collected = listing["jobs"] if page == 1 else collected + listing["jobs"]
                page_count, page = listing["page_count"], page + 1
                if page > min(page_count, MAX_LIST_PAGES):
                    cards = self._cards = collected
                    self._cards_read_at = time.monotonic()

            matched = [
                card for card in cards
                if matches_query(card, query) and (not location_key or location_key in card["location"].casefold())
            ]
            jobs = []
            for index, card in enumerate(matched):
                if card["url"] in self._details:
                    card = {**card, **self._details[card["url"]]}
                elif index < MAX_DETAIL_PAGES and robots_allows(card["url"]):
                    time.sleep(REQUEST_DELAY_SECONDS)
                    try:
                        detail = client.get(card["url"])
                        detail.raise_for_status()
                        self._details[card["url"]] = parse_detail(detail.text)
                        card = {**card, **self._details[card["url"]]}
                    except httpx.HTTPError:
                        pass  # keep the listing-level record; one broken job page must not drop the scan
                normalized = normalize_job(card, "techcareer")
                if normalized:
                    jobs.append(normalized)
        return jobs
