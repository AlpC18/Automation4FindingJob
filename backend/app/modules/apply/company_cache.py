"""
Company Research Cache
Adapted from MadsLorentzen/ai-job-search company research cache concept.

Caches company research results (website scrapes, LinkedIn data, news, mission)
to avoid redundant API calls and web fetches. Especially useful when:
- Multiple jobs from the same company are being evaluated
- /apply and /interview both need company context
- Rate limits on web search APIs

Storage: JSON file per company in data/company_research/
TTL: 7 days by default (configurable)
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from backend.app.core.config import settings
from backend.app.core.event_logger import agent_logger

CACHE_DIR = settings.DATA_PATH / "company_research"
CACHE_DIR.mkdir(exist_ok=True, parents=True)

DEFAULT_TTL_DAYS = 7


def _company_cache_key(company_name: str) -> str:
    """Generate a safe filename from company name."""
    slug = company_name.strip().lower()
    slug = "".join(c if c.isalnum() else "-" for c in slug).strip("-")
    if len(slug) > 60:
        digest = hashlib.sha1(slug.encode()).hexdigest()[:8]
        slug = f"{slug[:50]}-{digest}"
    return slug or "unknown"


def _cache_path(company_name: str) -> Path:
    return CACHE_DIR / f"{_company_cache_key(company_name)}.json"


class CompanyResearchCache:
    """Persistent JSON-based cache for company research data."""

    def __init__(self, ttl_days: int = DEFAULT_TTL_DAYS):
        self.ttl = timedelta(days=ttl_days)

    def get(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached research for a company. Returns None if expired or missing."""
        path = _cache_path(company_name)
        if not path.is_file():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        # Check TTL
        cached_at = data.get("_cached_at")
        if cached_at:
            try:
                cached_time = datetime.fromisoformat(cached_at)
                if datetime.now() - cached_time > self.ttl:
                    agent_logger.log_event(
                        "COMPANY_CACHE",
                        f"Cache expired for '{company_name}' (cached {cached_at})"
                    )
                    return None
            except ValueError:
                return None

        agent_logger.log_event(
            "COMPANY_CACHE",
            f"Cache HIT for '{company_name}' (cached {cached_at})"
        )
        return data

    def put(self, company_name: str, research_data: Dict[str, Any]) -> None:
        """Store research results for a company."""
        research_data["_cached_at"] = datetime.now().isoformat()
        research_data["_company_name"] = company_name

        path = _cache_path(company_name)
        path.write_text(
            json.dumps(research_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        agent_logger.log_event(
            "COMPANY_CACHE",
            f"Cached research for '{company_name}' → {path.name}"
        )

    def invalidate(self, company_name: str) -> bool:
        """Remove cached data for a company."""
        path = _cache_path(company_name)
        if path.is_file():
            path.unlink()
            return True
        return False

    def list_cached(self) -> list:
        """List all cached companies with their cache timestamps."""
        entries = []
        for f in CACHE_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                entries.append({
                    "company": data.get("_company_name", f.stem),
                    "cached_at": data.get("_cached_at", "unknown"),
                    "file": f.name,
                })
            except (json.JSONDecodeError, OSError):
                continue
        return sorted(entries, key=lambda e: e.get("cached_at", ""), reverse=True)

    def get_or_research(
        self,
        company_name: str,
        research_fn,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get from cache or execute research function and cache the result.

        Args:
            company_name: Company to research
            research_fn: Callable that performs the actual research.
                         Should return a dict with research data.
            **kwargs: Additional arguments passed to research_fn.
        """
        cached = self.get(company_name)
        if cached:
            return cached

        agent_logger.log_event(
            "COMPANY_CACHE",
            f"Cache MISS for '{company_name}', executing research..."
        )

        result = research_fn(company_name, **kwargs)
        if result:
            self.put(company_name, result)
        return result or {}

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        all_files = list(CACHE_DIR.glob("*.json"))
        total_size = sum(f.stat().st_size for f in all_files)
        expired = 0
        for f in all_files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                cached_at = data.get("_cached_at")
                if cached_at:
                    cached_time = datetime.fromisoformat(cached_at)
                    if datetime.now() - cached_time > self.ttl:
                        expired += 1
            except (json.JSONDecodeError, OSError, ValueError):
                expired += 1

        return {
            "total_entries": len(all_files),
            "expired_entries": expired,
            "active_entries": len(all_files) - expired,
            "total_size_kb": round(total_size / 1024, 1),
            "cache_dir": str(CACHE_DIR),
            "ttl_days": self.ttl.days,
        }


# Module-level singleton
company_cache = CompanyResearchCache()
