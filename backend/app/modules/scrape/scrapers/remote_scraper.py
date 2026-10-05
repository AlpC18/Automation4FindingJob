"""Key-free job feeds and public company career boards."""

from typing import Any, Dict, List

from backend.app.modules.scrape.live_sources import company_board_job_sources, public_remote_job_sources


class GlobalRemoteScraper:
    def __init__(self):
        self.platform_name = "remote"

    def fetch_jobs(self, query: str = "Senior Engineer", location: str = None) -> List[Dict[str, Any]]:
        return public_remote_job_sources.fetch(query, location=location)

    @property
    def answered_sources(self):
        return public_remote_job_sources.answered


class CompanyBoardsScraper:
    def __init__(self):
        self.platform_name = "company_boards"

    def fetch_jobs(self, query: str = "Senior Engineer", location: str = None) -> List[Dict[str, Any]]:
        return company_board_job_sources.fetch(query, location=location)

    @property
    def answered_sources(self):
        return company_board_job_sources.answered
