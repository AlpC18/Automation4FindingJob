"""Live job sources and normalization shared by portal adapters."""

import hashlib
import json
import re
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import quote

import httpx

from backend.app.core.config import settings
from backend.app.core.database import get_db_connection
from backend.app.modules.scrape.source_registry import get_source_config, list_company_boards
from backend.app.modules.scrape.apify_budget import invalidate_apify_token_usage, select_apify_account
from backend.app.modules.scrape.public_feeds import COMPANY_BOARD_PROVIDERS, PUBLIC_FEEDS


def _text(item: Dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return re.sub(r"<[^>]+>", " ", str(value)).strip()
    return default


def normalize_job(item: Dict[str, Any], platform: str) -> Optional[Dict[str, Any]]:
    """Convert source-specific job records into the database/API contract."""
    title = _text(item, "title", "position", "job_title", "name")
    company = _text(item, "company", "company_name", "companyName", "organization", "employer", default="Unknown employer")
    description = _text(item, "description", "description_text", "summary", "snippet")
    url = _text(item, "url", "job_url", "jobUrl", "apply_url", "applyUrl", "link", "canonical_url")
    if not title or not url:
        return None

    source_id = _text(item, "id", "job_id", "slug")
    stable_key = source_id or url or f"{platform}:{title}:{company}"
    identifier = f"{platform}_{hashlib.sha256(stable_key.encode('utf-8')).hexdigest()[:24]}"

    tags = item.get("tags") or item.get("skills") or []
    if isinstance(tags, str):
        tags = [tag.strip() for tag in re.split(r"[,|]", tags) if tag.strip()]
    remote_value = item.get("remote")
    remote_type = _text(item, "remote_type", "workplace_type", "workType")
    if not remote_type and (remote_value is True or str(remote_value).lower() in {"true", "1", "yes"}):
        remote_type = "Remote"
    if not remote_type:
        remote_type = "Unknown"

    salary = _text(item, "salary", "salary_range", "compensation")
    if not salary and (item.get("salary_min") or item.get("salary_max")):
        salary = f"{item.get('salary_min', '')} - {item.get('salary_max', '')} {item.get('salary_currency', '')}".strip()

    posted = _text(item, "date", "posted_at", "postedAt", "publishedAt", "created_at", "publication_date", "posted_date")
    deadline_match = re.match(r"\d{4}-\d{2}-\d{2}", _text(item, "deadline", "application_deadline", "applicationDeadline", "expires_at"))
    return {
        "id": identifier,
        "title": title,
        "company": company,
        "platform": platform,
        "url": url,
        "location": _text(item, "location", "candidate_required_location", "city", default="Unspecified"),
        "remote_type": remote_type,
        "salary_range": salary or "Not disclosed",
        "description": description or title,
        "posted_date": posted or "Unknown",
        "deadline": deadline_match.group(0) if deadline_match else "",
        "applicants_count": int(item.get("applicants_count") or 0) if str(item.get("applicants_count") or "0").isdigit() else 0,
        "source_tags": tags if isinstance(tags, list) else [],
    }


def _matches_query(job: Dict[str, Any], query: str) -> bool:
    terms = [term.lower() for term in re.findall(r"[\w+#.-]+", query) if len(term) > 1]
    if not terms:
        return True
    haystack = " ".join((job.get("title", ""), job.get("company", ""), job.get("description", ""), " ".join(job.get("source_tags", [])))).lower()
    return all(term in haystack for term in terms)


def _decode_actor_input(raw: str, query: str, location: Optional[str], actor_id: str = "") -> Dict[str, Any]:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("Apify actor input must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Apify actor input must be a JSON object")
    if actor_id.lower() == "valig/linkedin-jobs-scraper":
        payload.setdefault("keywords", query)
        payload.setdefault("limit", 100)
    else:
        payload.setdefault("query", query)
        payload.setdefault("searchQuery", query)
        payload.setdefault("keyword", query)
    if location:
        payload.setdefault("location", location)
    return payload


class ApifyActorJobSource:
    """Runs a user-selected Apify Actor synchronously and normalizes its dataset."""

    def test_connection(self, platform: str, actor_id_override: Optional[str] = None,
                        api_token_override: Optional[str] = None,
                        input_json_override: Optional[str] = None) -> Dict[str, Any]:
        """Validate Actor credentials without starting a billable run or saving them."""
        source_config = get_source_config(platform)
        actor_id = (actor_id_override if actor_id_override is not None else source_config["actor_id"])
        actor_id = (actor_id or getattr(settings, f"APIFY_ACTOR_{platform.upper()}", "")).strip()
        api_tokens = (
            list(dict.fromkeys(item.strip() for item in api_token_override.replace(",", "\n").splitlines() if item.strip()))
            if api_token_override else source_config.get("api_tokens") or ([settings.APIFY_API_TOKEN] if settings.APIFY_API_TOKEN else [])
        )
        if not api_tokens:
            raise RuntimeError("Apify API token is not configured.")
        if not actor_id:
            raise RuntimeError("Apify Actor ID is not configured.")
        input_json = input_json_override if input_json_override is not None else (
            source_config["input_json"] if source_config["has_custom_config"]
            else getattr(settings, f"APIFY_INPUT_{platform.upper()}", "{}")
        )
        _decode_actor_input(input_json, "connection test", None, actor_id)
        actor_path = quote(actor_id, safe="~")
        failures = 0
        for api_token in api_tokens:
            try:
                headers = {"Accept": "application/json", "Authorization": f"Bearer {api_token}"}
                account = httpx.get("https://api.apify.com/v2/users/me", headers=headers, timeout=12)
                if account.status_code >= 400 or not (account.json().get("data") or {}).get("id"):
                    failures += 1
                    continue
                response = httpx.get(f"https://api.apify.com/v2/acts/{actor_path}", headers=headers, timeout=15)
            except (httpx.HTTPError, ValueError, TypeError):
                raise RuntimeError("Could not reach the Apify API. Check the network and try again.")
            if response.status_code >= 400:
                raise RuntimeError(f"Apify returned HTTP {response.status_code} while checking the Actor.")
            payload = response.json()
            actor = payload.get("data", {}) if isinstance(payload, dict) else {}
            return {"source": platform, "actor_id": actor_id, "actor_name": actor.get("name"), "status": "connected", "verified_tokens": len(api_tokens) - failures}
        raise RuntimeError("No valid Apify account token was found. Refresh quota status and replace rejected keys.")

    def fetch(self, platform: str, query: str, location: Optional[str] = None) -> List[Dict[str, Any]]:
        source_config = get_source_config(platform)
        if not source_config["enabled"]:
            raise RuntimeError(f"{platform}: source disabled in source settings")
        actor_id = (source_config["actor_id"] or getattr(settings, f"APIFY_ACTOR_{platform.upper()}", "")).strip()
        api_token, account_remaining = select_apify_account(platform, settings.APIFY_MAX_TOTAL_CHARGE_USD)
        if not actor_id:
            raise RuntimeError(f"{platform}: configure APIFY_ACTOR_{platform.upper()} to enable this source")

        input_json = source_config["input_json"] if source_config["has_custom_config"] else getattr(settings, f"APIFY_INPUT_{platform.upper()}", "{}")
        payload = _decode_actor_input(input_json, query, location, actor_id)
        if actor_id.lower() == "valig/linkedin-jobs-scraper":
            payload["keywords"] = query
            if location:
                payload["location"] = location
            payload["limit"] = min(int(payload.get("limit") or 100), int(settings.APIFY_MAX_ITEMS_PER_RUN), 1000)
        connection = get_db_connection()
        try:
            today_start = time.time() - (time.time() % 86400)
            row = connection.cursor().execute(
                "SELECT COUNT(*) AS total FROM job_source_runs WHERE source = ? AND started_at >= ?",
                (platform, today_start),
            ).fetchone()
            daily_runs = int(row["total"] if row else 0)
        finally:
            connection.close()
        daily_limit = max(0, int(settings.APIFY_MAX_ACTOR_RUNS_PER_DAY))
        if daily_limit and daily_runs >= daily_limit:
            raise RuntimeError(f"Apify daily run limit reached ({daily_limit}). Increase APIFY_MAX_ACTOR_RUNS_PER_DAY to allow more runs.")
        actor_path = quote(actor_id, safe="~")
        endpoint = f"https://api.apify.com/v2/acts/{actor_path}/run-sync-get-dataset-items"
        max_items = max(1, min(int(settings.APIFY_MAX_ITEMS_PER_RUN), 1000))
        max_charge = min(float(settings.APIFY_MAX_TOTAL_CHARGE_USD), account_remaining, 100.0)
        if max_charge <= 0:
            raise RuntimeError("Seçilen Apify hesabının kalan güvenli harcama sınırı yetersiz.")
        try:
            response = httpx.post(
                endpoint,
                params={"timeout": settings.APIFY_TIMEOUT_SECONDS, "maxItems": max_items, "maxTotalChargeUsd": max_charge},
                json=payload,
                headers={"Accept": "application/json", "Authorization": f"Bearer {api_token}"},
                timeout=settings.APIFY_TIMEOUT_SECONDS + 10,
            )
        finally:
            # The Actor can incur cost even when the client times out or gets an error.
            invalidate_apify_token_usage(api_token)
        if response.status_code >= 400:
            raise RuntimeError(f"Apify {platform} Actor returned HTTP {response.status_code}: {response.text[:240]}")
        data = response.json()
        if not isinstance(data, list):
            raise RuntimeError(f"Apify {platform} Actor returned a non-list dataset")
        jobs = [normalized for item in data if isinstance(item, dict) if (normalized := normalize_job(item, platform))]
        jobs = [job for job in jobs if _matches_query(job, query)]
        if location:
            location_key = location.strip().casefold()
            jobs = [job for job in jobs if location_key in (job.get("location") or "").casefold()]
        return jobs[:max_items]


def _fetch_public_sources(
    sources: List[Tuple[str, str, Callable[[Any], List[Dict[str, Any]]]]],
    query: str,
    location: Optional[str],
) -> Tuple[List[Dict[str, Any]], Set[str]]:
    """Read (platform, url, mapper) sources; return matching jobs and the platforms that answered."""
    headers = {"Accept": "application/json", "User-Agent": settings.JOB_SOURCE_USER_AGENT}
    client = httpx.Client(timeout=httpx.Timeout(settings.JOB_SOURCE_TIMEOUT_SECONDS), headers=headers, follow_redirects=True)
    results: List[Dict[str, Any]] = []
    answered: Set[str] = set()
    failures: List[str] = []
    location_key = (location or "").strip().casefold()
    try:
        for platform, url, mapper in sources:
            try:
                response = client.get(url)
                response.raise_for_status()
                records = mapper(response.json())
            except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
                failures.append(f"{platform}: {str(exc)[:200]}")
                continue
            answered.add(platform)
            for item in records:
                job = normalize_job(item, platform)
                if not job or not _matches_query(job, query):
                    continue
                if location_key and location_key not in (job.get("location") or "").casefold():
                    continue
                results.append(job)
    finally:
        client.close()
    if not answered and failures:
        raise RuntimeError("; ".join(failures))
    return results, answered


class PublicRemoteJobSources:
    """Key-free remote job feeds, read live and normalized."""

    def __init__(self):
        self.answered: Set[str] = set()

    def fetch(self, query: str, location: Optional[str] = None) -> List[Dict[str, Any]]:
        sources = [(name, build_url(query), mapper) for name, build_url, mapper in PUBLIC_FEEDS]
        results, self.answered = _fetch_public_sources(sources, query, location)
        return results


class CompanyBoardJobSources:
    """Career boards of the companies listed in COMPANY_BOARDS (Greenhouse, Lever, Ashby)."""

    def __init__(self):
        self.answered: Set[str] = set()

    def verify(self, provider: str, slug: str) -> int:
        """Confirm a board exists before it is saved; returns how many jobs it currently lists."""
        build_url, mapper = COMPANY_BOARD_PROVIDERS[provider]
        headers = {"Accept": "application/json", "User-Agent": settings.JOB_SOURCE_USER_AGENT}
        try:
            response = httpx.get(build_url(slug), headers=headers, timeout=settings.JOB_SOURCE_TIMEOUT_SECONDS, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"{provider} şu an yanıt vermiyor; daha sonra tekrar dene.") from exc
        if response.status_code == 404:
            raise ValueError(f"{provider} üzerinde '{slug}' adında bir kariyer sayfası bulunamadı.")
        if response.status_code >= 400:
            raise RuntimeError(f"{provider} HTTP {response.status_code} döndürdü.")
        try:
            return len(mapper(response.json(), slug))
        except (ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(f"{provider} beklenmeyen bir yanıt döndürdü.") from exc

    def fetch(self, query: str, location: Optional[str] = None) -> List[Dict[str, Any]]:
        boards = [(board["provider"], board["slug"]) for board in list_company_boards()]
        if not boards:
            raise RuntimeError("company_boards: add a company career page under Sources (or set COMPANY_BOARDS) to enable this source")
        sources = []
        for provider, slug in boards:
            build_url, mapper = COMPANY_BOARD_PROVIDERS[provider]
            sources.append((provider, build_url(slug), lambda body, mapper=mapper, slug=slug: mapper(body, slug)))
        results, self.answered = _fetch_public_sources(sources, query, location)
        return results


apify_job_source = ApifyActorJobSource()
public_remote_job_sources = PublicRemoteJobSources()
company_board_job_sources = CompanyBoardJobSources()
