"""
Enhanced Company-Specific Salary Lookup
Adapted from MadsLorentzen/ai-job-search salary_lookup.py concept.

Extends existing salary_benchmark.py with:
- BYO salary data (JSON file with company-specific compensation)
- Fuzzy company name matching (handles legal suffixes, abbreviations)
- City/region filtering
- Data validation and audit
- Import from Excel/CSV

Storage: data/salary_data.json (user-maintained)
"""

import json
import hashlib
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from backend.app.core.json_store import read_json_store
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

from backend.app.core.config import settings
from backend.app.core.event_logger import agent_logger
from backend.app.core.tenant import get_tenant_id

SALARY_DATA_PATH = settings.DATA_PATH / "salary_data.json"


def salary_data_path_for_tenant(tenant_id: Optional[str] = None) -> Path:
    if not tenant_id:
        return SALARY_DATA_PATH
    safe_tenant = re.sub(r"[^a-zA-Z0-9]", "", tenant_id)
    return settings.DATA_PATH / "tenants" / safe_tenant / SALARY_DATA_PATH.name


def _normalize(text: str) -> str:
    """Normalize text for fuzzy comparison."""
    text = unicodedata.normalize("NFKD", text.lower().strip())
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9 ]", "", text).strip()


def _anglicize(text: str) -> str:
    """Remove diacritics for cross-locale matching."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _extract_core_words(text: str) -> List[str]:
    """Extract core words, stripping legal suffixes."""
    stop_suffixes = {"a/s", "aps", "as", "ltd", "inc", "gmbh", "bv", "ag", "sa", "llc", "co"}
    words = _normalize(text).split()
    return [w for w in words if w not in stop_suffixes and len(w) > 1]


def assess_salary_evidence(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Score how completely a salary entry documents its evidence, not truth."""
    score = 0
    source_name = str(entry.get("source_name") or "").strip()
    source_url = str(entry.get("source_url") or "").strip()
    if source_name:
        score += 20
    parsed_url = urlparse(source_url)
    if parsed_url.scheme in {"http", "https"} and parsed_url.netloc:
        score += 20

    as_of = entry.get("as_of") or ""
    try:
        report_date = date.fromisoformat(str(as_of)[:10])
        age_days = max(0, (datetime.now(timezone.utc).date() - report_date).days)
        score += 25 if age_days <= 365 else 10 if age_days <= 730 else 0
        freshness = "current" if age_days <= 365 else "aging" if age_days <= 730 else "outdated"
    except (TypeError, ValueError):
        freshness = "unknown"

    sample_size = entry.get("sample_size")
    if isinstance(sample_size, (int, float)) and sample_size > 0:
        score += 25 if sample_size >= 10 else 15 if sample_size >= 5 else 5
    source_count = entry.get("source_count")
    if isinstance(source_count, (int, float)) and source_count >= 2:
        score += 10

    level = "well_documented" if score >= 70 else "partially_documented" if score >= 40 else "limited_evidence"
    return {
        "score": score,
        "level": level,
        "freshness": freshness,
        "independently_verified": False,
        "note": "Evidence metadata completeness only; the source and figures have not been independently verified.",
    }


class SalaryLookup:
    """Company-specific salary benchmark lookup with fuzzy matching."""

    def __init__(self, data_path: Path = SALARY_DATA_PATH):
        self.base_data_path = data_path
        self.data_path = data_path
        self._loaded_path: Optional[Path] = None
        self._data: Dict[str, Any] = {}
        self._load()

    def _ensure_tenant_data(self) -> None:
        tenant_id = get_tenant_id()
        active_path = salary_data_path_for_tenant(tenant_id) if self.base_data_path == SALARY_DATA_PATH else self.base_data_path
        if tenant_id and self.base_data_path != SALARY_DATA_PATH:
            safe_tenant = re.sub(r"[^a-zA-Z0-9]", "", tenant_id)
            active_path = self.base_data_path.parent / "tenants" / safe_tenant / self.base_data_path.name
        if active_path != self._loaded_path:
            self.data_path = active_path
            self._load()

    def reload_current(self) -> None:
        """Reload the active user's file after an external lifecycle operation."""
        self._loaded_path = None
        self._ensure_tenant_data()

    def _load(self):
        """Load salary data from disk."""
        self._loaded_path = self.data_path
        if self.data_path.is_file():
            self._data = read_json_store(self.data_path, {"metadata": {}, "companies": []})
        else:
            self._data = {
                "metadata": {
                    "source": "User-provided salary data",
                    "last_updated": "",
                    "currency": "USD",
                    "period": "year",
                },
                "companies": [],
            }

    def _save(self):
        """Persist salary data to disk."""
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.data_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def search(
        self,
        query: str,
        city: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for a company by name with fuzzy matching.
        Returns matching entries sorted by relevance.
        """
        self._ensure_tenant_data()
        companies = self._data.get("companies", [])
        if not companies:
            return []

        q_norm = _normalize(query)
        q_ang = _anglicize(q_norm)
        q_words = set(_extract_core_words(query))

        scored = []
        for entry in companies:
            company_name = entry.get("company", "")

            # City filter
            if city:
                entry_city = (entry.get("city") or "").lower()
                if city.lower() not in entry_city and _anglicize(city) not in _anglicize(entry_city):
                    continue

            score = self._match_score(q_norm, q_ang, q_words, company_name)
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: (-x[0], x[1].get("company", "")))
        return [dict(entry, evidence=assess_salary_evidence(entry)) for score, entry in scored if score >= 30]

    def _match_score(
        self,
        q_norm: str,
        q_ang: str,
        q_words: set,
        entry_name: str,
    ) -> int:
        """Compute fuzzy match score between query and company name."""
        e_norm = _normalize(entry_name)
        e_ang = _anglicize(e_norm)

        # Exact match
        if q_norm == e_norm or q_ang == e_ang:
            return 100

        # Substring
        if q_norm in e_norm or q_ang in e_ang:
            return 85

        if e_norm in q_norm or e_ang in q_ang:
            return 80

        # Word overlap
        e_words = set(_extract_core_words(entry_name))
        if q_words and e_words:
            overlap = q_words & e_words
            if overlap:
                coverage = len(overlap) / len(q_words)
                return int(30 + coverage * 40)

        return 0

    def add_company(
        self,
        company: str,
        city: str = "",
        salary_min: Optional[float] = None,
        salary_median: Optional[float] = None,
        salary_max: Optional[float] = None,
        currency: str = "USD",
        period: str = "year",
        categories: Optional[Dict[str, Any]] = None,
        notes: str = "",
        source_type: str = "user_reported",
        source_name: str = "",
        source_url: str = "",
        as_of: str = "",
        sample_size: Optional[int] = None,
        source_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Add or update a company salary entry."""
        self._ensure_tenant_data()
        entry = {
            "company": company,
            "city": city,
            "salary_min": salary_min,
            "salary_median": salary_median,
            "salary_max": salary_max,
            "currency": currency,
            "period": period,
            "categories": categories or {},
            "notes": notes,
            "source_type": source_type,
            "source_name": source_name.strip(),
            "source_url": source_url.strip(),
            "as_of": as_of,
            "sample_size": sample_size,
            "source_count": source_count,
        }
        entry["evidence"] = assess_salary_evidence(entry)

        # Check if exists and update
        companies = self._data.get("companies", [])
        existing_idx = None
        for i, c in enumerate(companies):
            if _normalize(c.get("company", "")) == _normalize(company):
                if not city or _normalize(c.get("city", "")) == _normalize(city):
                    existing_idx = i
                    break

        if existing_idx is not None:
            companies[existing_idx] = entry
            action = "updated"
        else:
            companies.append(entry)
            action = "added"

        self._data["companies"] = companies
        self._save()

        agent_logger.log_event("SALARY_LOOKUP", f"Company {action}: {company} ({city})")
        return {"action": action, "entry": entry}

    def import_from_list(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Bulk import salary entries."""
        added = 0
        updated = 0
        errors = []

        for entry in entries:
            try:
                result = self.add_company(
                    company=entry.get("company", ""),
                    city=entry.get("city", ""),
                    salary_min=entry.get("salary_min"),
                    salary_median=entry.get("salary_median"),
                    salary_max=entry.get("salary_max"),
                    currency=entry.get("currency", "USD"),
                    period=entry.get("period", "year"),
                    notes=entry.get("notes", ""),
                    source_type=entry.get("source_type", "user_reported"),
                    source_name=entry.get("source_name", ""),
                    source_url=entry.get("source_url", ""),
                    as_of=entry.get("as_of", ""),
                    sample_size=entry.get("sample_size"),
                    source_count=entry.get("source_count"),
                )
                if result["action"] == "added":
                    added += 1
                else:
                    updated += 1
            except Exception as e:
                errors.append({"entry": entry, "error": str(e)})

        return {
            "added": added,
            "updated": updated,
            "errors": len(errors),
            "error_details": errors,
        }

    def validate(self) -> Dict[str, Any]:
        """Validate salary data for consistency."""
        self._ensure_tenant_data()
        companies = self._data.get("companies", [])
        errors = []
        warnings = []

        for i, entry in enumerate(companies):
            company = entry.get("company", "")

            if not company:
                errors.append(f"Entry {i}: missing company name")

            s_min = entry.get("salary_min")
            s_med = entry.get("salary_median")
            s_max = entry.get("salary_max")

            if s_min and s_max and s_min > s_max:
                errors.append(f"{company}: min ({s_min}) > max ({s_max})")

            if s_med:
                if s_min and s_med < s_min:
                    warnings.append(f"{company}: median ({s_med}) < min ({s_min})")
                if s_max and s_med > s_max:
                    warnings.append(f"{company}: median ({s_med}) > max ({s_max})")

        return {
            "total_entries": len(companies),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
            "is_valid": len(errors) == 0,
        }

    def format_entry(self, entry: Dict[str, Any]) -> str:
        """Format a salary entry for display."""
        company = entry.get("company", "Unknown")
        city = entry.get("city", "")
        currency = entry.get("currency", "USD")
        period = entry.get("period", "year")

        parts = [f"\n📊 {company}"]
        if city:
            parts[0] += f" ({city})"

        s_min = entry.get("salary_min")
        s_med = entry.get("salary_median")
        s_max = entry.get("salary_max")

        if s_min and s_max:
            parts.append(f"   Range: {currency} {s_min:,.0f} – {s_max:,.0f} / {period}")
        if s_med:
            parts.append(f"   Median: {currency} {s_med:,.0f} / {period}")

        notes = entry.get("notes")
        if notes:
            parts.append(f"   Note: {notes}")

        return "\n".join(parts)

    def stats(self) -> Dict[str, Any]:
        """Return salary data statistics."""
        self._ensure_tenant_data()
        companies = self._data.get("companies", [])
        cities = set(c.get("city", "") for c in companies if c.get("city"))
        currencies = set(c.get("currency", "") for c in companies if c.get("currency"))

        return {
            "total_companies": len(companies),
            "unique_cities": len(cities),
            "currencies": list(currencies),
            "metadata": self._data.get("metadata", {}),
        }


# Module-level singleton
salary_lookup = SalaryLookup()
