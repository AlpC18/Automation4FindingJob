"""LinkedIn job source backed by the configured Apify Actor."""

from typing import Any, Dict, List

from backend.app.modules.scrape.live_sources import apify_job_source


class LinkedInScraper:
    def __init__(self):
        self.platform_name = "linkedin"

    def fetch_jobs(self, query: str = "Software Engineer", location: str = None) -> List[Dict[str, Any]]:
        return apify_job_source.fetch("linkedin", query, location)
