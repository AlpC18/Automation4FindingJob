"""Upwork job source backed by the configured Apify Actor."""

from typing import Any, Dict, List

from backend.app.modules.scrape.live_sources import apify_job_source


class UpworkScraper:
    def __init__(self):
        self.platform_name = "upwork"

    def fetch_jobs(self, query: str = "FastAPI Next.js", location: str = None) -> List[Dict[str, Any]]:
        return apify_job_source.fetch("upwork", query, location)
