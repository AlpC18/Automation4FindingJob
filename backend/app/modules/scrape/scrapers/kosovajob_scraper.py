"""KosovaJob source: reads the site's public search pages directly (no API key needed).

robots.txt allows crawling; requests are sequential, rate limited and capped per scan.
A user-configured Apify Actor, when present, takes precedence.
"""

import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from backend.app.core.config import settings
from backend.app.modules.scrape.live_sources import apify_job_source, normalize_job
from backend.app.modules.scrape.robots import robots_allows
from backend.app.modules.scrape.source_registry import get_source_config

BASE_URL = "https://kosovajob.com/"
MAX_DETAIL_PAGES = 25
DETAIL_DELAY_SECONDS = 0.4


def _text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def parse_listing(page_html: str) -> List[Dict[str, str]]:
    """Job cards on a KosovaJob list/search page: title, detail URL, city and company slug."""
    jobs, seen = [], set()
    for card in BeautifulSoup(page_html, "html.parser").select(".jobListCnts"):
        title_node = card.select_one(".jobListTitle")
        link, title = card.find("a", href=True), _text(title_node)
        if not link or not title:
            continue
        parts = urlsplit(link["href"])
        segments = [segment for segment in parts.path.split("/") if segment]
        # Only real job pages (https://kosovajob.com/<company>/<job>); ads and off-site links are skipped.
        if parts.scheme != "https" or parts.hostname != "kosovajob.com" or len(segments) != 2 or link["href"] in seen:
            continue
        seen.add(link["href"])
        city = _text(card.select_one(".jobListCity"))
        jobs.append({
            "title": title,
            "url": link["href"],
            "company": segments[0].replace("-", " ").title(),
            "location": f"{city}, Kosovo" if city else "Kosovo",
            # The card's `date` attribute is the application deadline, not the posting date.
            "deadline": str(title_node.get("date") or ""),
        })
    return jobs


def parse_detail(page_html: str) -> Dict[str, Any]:
    """Company name, full description and tags from a KosovaJob job page."""
    soup = BeautifulSoup(page_html, "html.parser")
    description = soup.find("meta", attrs={"property": "og:description"})
    return {key: value for key, value in {
        "company": _text(soup.select_one(".containerLeftAreaTopAreaRightTitleComp")),
        "description": (description.get("content") or "").strip() if description else "",
        "tags": list(dict.fromkeys(_text(tag) for tag in soup.select(".tagCnt") if _text(tag))),
    }.items() if value}


class KosovaJobScraper:
    def __init__(self):
        self.platform_name = "kosovajob"

    def fetch_jobs(self, query: str = "Software Engineer", location: str = None) -> List[Dict[str, Any]]:
        config = get_source_config("kosovajob")
        if config["has_custom_config"] and config["actor_id"]:
            return apify_job_source.fetch("kosovajob", query, location)
        return self._scrape(query, location)

    def _scrape(self, query: str, location: Optional[str]) -> List[Dict[str, Any]]:
        headers = {"User-Agent": settings.JOB_SOURCE_USER_AGENT, "Accept": "text/html"}
        location_key = (location or "").strip().casefold()
        if not robots_allows(BASE_URL):
            raise RuntimeError("kosovajob: the site's robots.txt does not allow reading the job list")
        with httpx.Client(timeout=settings.JOB_SOURCE_TIMEOUT_SECONDS, headers=headers, follow_redirects=True) as client:
            response = client.get(BASE_URL, params={"q": query})
            response.raise_for_status()
            cards = [card for card in parse_listing(response.text) if not location_key or location_key in card["location"].casefold()]
            jobs = []
            for index, card in enumerate(cards):
                if index < MAX_DETAIL_PAGES and robots_allows(card["url"]):
                    if index:
                        time.sleep(DETAIL_DELAY_SECONDS)
                    try:
                        detail = client.get(card["url"])
                        detail.raise_for_status()
                        card = {**card, **parse_detail(detail.text)}
                    except httpx.HTTPError:
                        pass  # keep the listing-level record; one broken job page must not drop the scan
                normalized = normalize_job(card, "kosovajob")
                if normalized:
                    jobs.append(normalized)
        return jobs
