"""Small, deterministic rules for job normalization, deduplication and freshness."""

import re
from datetime import date, datetime, timedelta
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").casefold()))


def canonical_job_key(job: dict[str, Any]) -> str:
    url = (job.get("url") or "").strip()
    if url:
        parts = urlsplit(url)
        query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_") and k.lower() not in {"ref", "source", "trk"}])
        return "url:" + urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))
    return "job:" + _normalized(job.get("title", "")) + "|" + _normalized(job.get("company", ""))


def job_match_keys(job: dict[str, Any]) -> tuple[str, ...]:
    keys = [canonical_job_key(job)]
    title_company = "job:" + _normalized(job.get("title", "")) + "|" + _normalized(job.get("company", ""))
    if title_company not in keys and title_company != "job:|":
        keys.append(title_company)
    return tuple(keys)


def quality_issue(job: dict[str, Any], *, now: Optional[date] = None) -> Optional[str]:
    if not (job.get("title") or "").strip() or not (job.get("company") or "").strip():
        return "missing_title_or_company"
    description = (job.get("description") or "").strip()
    if not job.get("url") and len(description) < 80:
        return "insufficient_job_details"
    posted = (job.get("posted_date") or "").strip()
    today = now or datetime.now().date()
    try:
        posted_day = datetime.fromisoformat(posted.replace("Z", "+00:00")).date()
        if posted_day < today - timedelta(days=90):
            return "expired_over_90_days"
    except ValueError:
        pass
    relative = posted.casefold()
    age_match = re.search(r"(\d+)\s*(days?|d|weeks?|w|months?|mo|ay|hafta|gün)", relative)
    if age_match:
        amount = int(age_match.group(1))
        unit = age_match.group(2)
        age_days = amount * (30 if unit.startswith(("month", "mo", "ay")) else 7 if unit.startswith(("week", "w", "hafta")) else 1)
        if age_days >= 90:
            return "expired_over_90_days"
    return None
