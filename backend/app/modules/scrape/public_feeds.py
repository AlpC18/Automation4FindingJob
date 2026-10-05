"""Key-free job feeds and public company career boards (Greenhouse, Lever, Ashby).

Every mapper converts one provider's payload into the field names `normalize_job`
already understands, so the rest of the pipeline stays provider-agnostic.
"""

import html
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Tuple
from urllib.parse import urlencode, urlsplit

from backend.app.core.config import settings

Record = Dict[str, Any]

_BOARD_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,60}$")


def _iso(timestamp: Any, *, milliseconds: bool = False) -> str:
    """Epoch timestamp -> ISO date string; empty when the provider sent nothing usable."""
    try:
        return datetime.fromtimestamp(float(timestamp) / (1000 if milliseconds else 1), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def _present(record: Record) -> Record:
    return {key: value for key, value in record.items() if value not in (None, "", [])}


def _dicts(value: Any) -> List[Record]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _listing(body: Any) -> List[Record]:
    """RemoteOK returns a bare list; Arbeitnow wraps it in {"data": [...]}."""
    return _dicts(body if isinstance(body, list) else (body or {}).get("data"))


def _remotive(body: Any) -> List[Record]:
    return [{**job, "remote": True} for job in _dicts((body or {}).get("jobs"))]


def _jobicy(body: Any) -> List[Record]:
    return [_present({
        "id": job.get("id"), "title": job.get("jobTitle"), "company": job.get("companyName"), "url": job.get("url"),
        "description": job.get("jobDescription") or job.get("jobExcerpt"), "location": job.get("jobGeo"),
        "date": job.get("pubDate"), "tags": job.get("jobIndustry"), "remote": True,
        "salary_min": job.get("salaryMin"), "salary_max": job.get("salaryMax"), "salary_currency": job.get("salaryCurrency"),
    }) for job in _dicts((body or {}).get("jobs"))]


def _himalayas(body: Any) -> List[Record]:
    jobs = []
    for job in _dicts((body or {}).get("jobs")):
        countries = job.get("locationRestrictions") or []
        has_salary = job.get("minSalary") or job.get("maxSalary")
        jobs.append(_present({
            "title": job.get("title"), "company": job.get("companyName"),
            "url": job.get("applicationLink") or job.get("guid"),
            "description": job.get("description") or job.get("excerpt"),
            "location": ", ".join(str(country) for country in countries[:5]) if isinstance(countries, list) and countries else "Worldwide",
            "date": _iso(job.get("pubDate")), "deadline": _iso(job.get("expiryDate")),
            "tags": job.get("categories"), "remote": True,
            "salary_min": job.get("minSalary"), "salary_max": job.get("maxSalary"),
            "salary_currency": job.get("currency") if has_salary else None,
        }))
    return jobs


# (source name, URL for a query, mapper). Each feed is public and needs no API key.
PUBLIC_FEEDS: Tuple[Tuple[str, Callable[[str], str], Callable[[Any], List[Record]]], ...] = (
    ("remoteok", lambda query: settings.REMOTEOK_API_URL, _listing),
    ("arbeitnow", lambda query: settings.ARBEITNOW_API_URL, _listing),
    ("remotive", lambda query: "https://remotive.com/api/remote-jobs?" + urlencode({"search": query}), _remotive),
    ("jobicy", lambda query: "https://jobicy.com/api/v2/remote-jobs?count=100", _jobicy),
    ("himalayas", lambda query: "https://himalayas.app/jobs/api/search?" + urlencode({"q": query, "limit": 20}), _himalayas),
)


def _company_name(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


def _greenhouse(body: Any, slug: str) -> List[Record]:
    return [_present({
        "id": f"greenhouse-{slug}-{job.get('id')}", "title": job.get("title"),
        "company": job.get("company_name") or _company_name(slug), "url": job.get("absolute_url"),
        "description": html.unescape(str(job.get("content") or "")),  # Greenhouse double-encodes its HTML
        "location": (job.get("location") or {}).get("name") if isinstance(job.get("location"), dict) else None,
        "date": job.get("first_published") or job.get("updated_at"), "deadline": job.get("application_deadline"),
    }) for job in _dicts((body or {}).get("jobs") if isinstance(body, dict) else None)]


def _lever(body: Any, slug: str) -> List[Record]:
    return [_present({
        "id": f"lever-{slug}-{job.get('id')}", "title": job.get("text"), "company": _company_name(slug),
        "url": job.get("hostedUrl"), "description": job.get("descriptionPlain"),
        "location": (job.get("categories") or {}).get("location") if isinstance(job.get("categories"), dict) else None,
        "workplace_type": job.get("workplaceType"), "date": _iso(job.get("createdAt"), milliseconds=True),
    }) for job in _dicts(body)]


def _ashby(body: Any, slug: str) -> List[Record]:
    return [_present({
        "id": f"ashby-{slug}-{job.get('id')}", "title": job.get("title"), "company": _company_name(slug),
        "url": job.get("jobUrl"), "description": job.get("descriptionPlain"), "location": job.get("location"),
        "workplace_type": job.get("workplaceType") or ("Remote" if job.get("isRemote") else None),
        "date": job.get("publishedAt"),
    }) for job in _dicts((body or {}).get("jobs") if isinstance(body, dict) else None) if job.get("isListed", True)]


# provider -> (URL for a company's board, mapper)
COMPANY_BOARD_PROVIDERS: Dict[str, Tuple[Callable[[str], str], Callable[[Any, str], List[Record]]]] = {
    "greenhouse": (lambda slug: f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", _greenhouse),
    "lever": (lambda slug: f"https://api.lever.co/v0/postings/{slug}?mode=json", _lever),
    "ashby": (lambda slug: f"https://api.ashbyhq.com/posting-api/job-board/{slug}", _ashby),
}


def parse_company_boards(raw: str) -> List[Tuple[str, str]]:
    """Parse COMPANY_BOARDS ("greenhouse:stripe,lever:spotify") into (provider, board slug) pairs."""
    boards: List[Tuple[str, str]] = []
    for entry in (raw or "").split(","):
        if not entry.strip():
            continue
        provider, _, slug = entry.strip().lower().partition(":")
        if provider not in COMPANY_BOARD_PROVIDERS or not _BOARD_SLUG.match(slug):
            raise ValueError(
                f"COMPANY_BOARDS entry '{entry.strip()}' is invalid; use provider:company with provider in "
                f"{', '.join(COMPANY_BOARD_PROVIDERS)} (e.g. greenhouse:stripe)."
            )
        if (provider, slug) not in boards:
            boards.append((provider, slug))
    return boards


_BOARD_HOSTS = {
    "boards.greenhouse.io": "greenhouse", "job-boards.greenhouse.io": "greenhouse",
    "jobs.lever.co": "lever", "jobs.ashbyhq.com": "ashby",
}


def parse_board_reference(text: str) -> Tuple[str, str]:
    """Accept "greenhouse:stripe" or a careers URL such as https://jobs.lever.co/spotify."""
    value = (text or "").strip()
    if "://" in value:
        parts = urlsplit(value)
        segments = [segment for segment in parts.path.split("/") if segment]
        provider = _BOARD_HOSTS.get((parts.hostname or "").lower())
        if not provider or not segments:
            raise ValueError(
                "Bu adres tanınmadı. boards.greenhouse.io/<şirket>, jobs.lever.co/<şirket> veya "
                "jobs.ashbyhq.com/<şirket> biçiminde bir kariyer sayfası adresi gir."
            )
        value = f"{provider}:{segments[0]}"
    try:
        boards = parse_company_boards(value)
    except ValueError as exc:
        raise ValueError("Şirket sayfası 'greenhouse:stripe' biçiminde ya da kariyer sayfası adresi olarak girilmeli.") from exc
    if len(boards) != 1:
        raise ValueError("Tek bir şirket sayfası gir.")
    return boards[0]
