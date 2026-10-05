"""
Unified Multi-Platform Scraper Coordinator
Coordinates scraping across LinkedIn, Upwork, Kosovajob, and Remote portals.
Applies account health rate limits, ghost job scoring, and saves to database.
"""

import json
import time
import uuid
from typing import List, Dict, Any, Optional
from backend.app.core.config import settings
from backend.app.core.database import get_db_connection
from backend.app.modules.scrape.rate_limiter import account_health
from backend.app.modules.scrape.ghost_job_detector import evaluate_ghost_job
from backend.app.modules.scrape.scrapers.linkedin_scraper import LinkedInScraper
from backend.app.modules.scrape.scrapers.upwork_scraper import UpworkScraper
from backend.app.modules.scrape.scrapers.kosovajob_scraper import KosovaJobScraper
from backend.app.modules.scrape.scrapers.remote_scraper import CompanyBoardsScraper, GlobalRemoteScraper
from backend.app.modules.scrape.scrapers.techcareer_scraper import TechcareerScraper
from backend.app.modules.scrape.apify_budget import mark_scan_start
from backend.app.modules.scrape.live_sources import apify_job_source
from backend.app.modules.scrape.source_registry import (
    ACTOR_SOURCES,
    create_scan_run,
    finish_scan_run,
    get_source_config,
    get_source_health,
    list_company_boards,
    record_source_run,
)
from backend.app.modules.scrape.job_quality import job_match_keys, quality_issue


def _count_current_jobs() -> int:
    conn = get_db_connection()
    try:
        row = conn.cursor().execute(
            "SELECT COUNT(*) AS total FROM scraped_jobs WHERE stale_at IS NULL AND COALESCE(status, 'Draft') IN ('Draft', 'New', '')"
        ).fetchone()
        return int(row["total"] if row else 0)
    finally:
        conn.close()


def _record_scan_notification(total: int, errors: list[str], scan_id: str):
    conn = get_db_connection()
    try:
        if errors:
            title = "İlan taraması kısmen tamamlandı"
            body = f"{total} canlı ilan işlendi. {len(errors)} kaynak hata verdi; kaynak sağlığını kontrol edin."
        else:
            title = "İlan taraması tamamlandı"
            body = f"{total} canlı ilan güncellendi. Tarama no: {scan_id[:8]}"
        conn.cursor().execute(
            "INSERT INTO user_notifications(id, title, body, href) VALUES (?, ?, ?, ?)",
            (uuid.uuid4().hex, title, body, "/jobs"),
        )
        conn.commit()
    finally:
        conn.close()


class ApifyPortalScraper:
    """Portal adapter for any source served by a user-configured Apify Actor."""

    def __init__(self, platform: str):
        self.platform_name = platform

    def fetch_jobs(self, query: str = "Software Engineer", location: str = None, remote: bool = False) -> List[Dict[str, Any]]:
        return apify_job_source.fetch(self.platform_name, query, location, remote)


def _default_platforms(known: List[str]) -> List[str]:
    """SCRAPER_PLATFORMS plus every Actor source the user enabled in source settings."""
    platforms = list(settings.scraper_platforms or known)
    for source in ACTOR_SOURCES:
        if source in platforms:
            continue
        config = get_source_config(source)
        if config["has_custom_config"] and config["enabled"] and config["actor_id"]:
            platforms.append(source)
    if list_company_boards() and "company_boards" not in platforms:
        platforms.append("company_boards")
    return platforms


class UnifiedScraper:
    def __init__(self):
        self.scrapers = {
            **{source: ApifyPortalScraper(source) for source in ACTOR_SOURCES},
            "linkedin": LinkedInScraper(),
            "upwork": UpworkScraper(),
            "kosovajob": KosovaJobScraper(),
            "remote": GlobalRemoteScraper(),
            "company_boards": CompanyBoardsScraper(),
            "techcareer": TechcareerScraper(),
        }

    def run_multi_platform_scrape(
        self,
        query: Optional[str] = None,
        target_platforms: List[str] = None,
        queries: Optional[List[str]] = None,
        location_preference: Optional[str] = None,
        remote_type: Optional[str] = None,
        replace_current_feed: bool = True,
    ) -> Dict[str, Any]:
        if settings.SCRAPER_MODE.lower() == "disabled":
            return {
                "status": "disabled",
                "total_scraped": 0,
                "jobs": [],
                "errors": ["Scraper SCRAPER_MODE=disabled ile kapatıldı."],
                "platform_health": account_health.get_all_platform_health(),
            }

        platforms_to_run = target_platforms or _default_platforms(list(self.scrapers.keys()))
        scraped_results = []
        errors = []
        successful_platforms = set()
        answered_sources = set()
        filtered = {"duplicates": 0, "low_quality": 0, "expired": 0, "location_mismatch": 0, "work_mode_mismatch": 0}
        raw_fetched_count = 0
        
        # Build search queries list
        requested_mode = str(remote_type or "").strip().casefold().replace("-", " ")
        if requested_mode == "all":
            requested_mode = ""
        active_queries = queries if (queries and len(queries) > 0) else [query or settings.DEFAULT_SCRAPE_QUERY]
        scan_id = create_scan_run(active_queries, platforms_to_run)
        if any(plat.lower() in ACTOR_SOURCES for plat in platforms_to_run):
            mark_scan_start()

        # Step 1: Scrape items across all active role queries
        for q in active_queries:
            for plat in platforms_to_run:
                plat_key = plat.lower()
                if plat_key not in self.scrapers:
                    errors.append(f"Unsupported source '{plat}'. Configured sources: {', '.join(self.scrapers)}")
                    continue
                    
                can_scrape, msg, metrics = account_health.can_perform_action(plat_key, action_type="scrape")
                if not can_scrape:
                    errors.append(f"{plat.capitalize()}: {msg}")
                    record_source_run(plat_key, "blocked", 0, msg, 0)
                    continue
                    
                started_at = time.monotonic()
                try:
                    scraper = self.scrapers[plat_key]
                    if isinstance(scraper, ApifyPortalScraper):
                        items = scraper.fetch_jobs(query=q, location=location_preference, remote=requested_mode == "remote")
                    else:
                        items = scraper.fetch_jobs(query=q, location=location_preference)
                    raw_fetched_count += len(items)
                    successful_platforms.add(plat_key)
                    # Only feeds that actually answered may have their old rows replaced.
                    answered_sources.update(
                        getattr(scraper, "answered_sources", None)
                        or ({"remoteok", "arbeitnow"} if plat_key == "remote" else {plat_key})
                    )
                    
                    for item in items:
                        # A user's preference is never written as source-provided job data.
                        source_location = str(item.get("location") or "").strip()
                        unknown_locations = {"", "unspecified", "unknown", "not specified"}
                        matched_by_source = item.pop("location_matched_by_source", False)
                        if location_preference and not matched_by_source and (source_location.casefold() in unknown_locations or location_preference.casefold() not in source_location.casefold()):
                            filtered["location_mismatch"] += 1
                            continue
                        source_mode = str(item.get("remote_type") or "Unknown").strip().casefold().replace("-", " ")
                        mode_aliases = {
                            "remote": {"remote", "fully remote", "remote work"},
                            "hybrid": {"hybrid", "remote / hybrid"},
                            "hybrid/remote": {"remote", "fully remote", "remote work", "hybrid", "remote / hybrid"},
                            "onsite": {"onsite", "on site", "office"},
                            "on site": {"onsite", "on site", "office"},
                        }
                        if requested_mode and source_mode not in mode_aliases.get(requested_mode, {requested_mode}):
                            filtered["work_mode_mismatch"] += 1
                            continue

                        ghost_score, ghost_reasons, rec = evaluate_ghost_job(item)
                        item["ghost_score"] = ghost_score
                        item["ghost_reasons"] = ghost_reasons
                        item["ghost_recommendation"] = rec
                        issue = quality_issue(item)
                        if issue:
                            filtered["expired" if issue.startswith("expired") else "low_quality"] += 1
                            continue
                        scraped_results.append(item)
                        
                    account_health.log_action(plat_key, "scrape", "SUCCESS", f"Fetched {len(items)} items for '{q}'")
                    record_source_run(plat_key, "success", len(items), None, (time.monotonic() - started_at) * 1000)
                except Exception as e:
                    errors.append(f"Error scraping {plat} for '{q}': {str(e)}")
                    account_health.log_action(plat_key, "scrape", "ERROR", str(e))
                    record_source_run(plat_key, "error", 0, str(e), (time.monotonic() - started_at) * 1000)
                
        # Step 2: Atomic DB write for all scraped jobs. A successful manual
        # scan is a fresh feed snapshot: remove old unprocessed rows from the
        # sources that actually answered, then upsert the new records. Rows
        # already in an application lifecycle stage are retained as history.
        new_jobs = []
        removed_count = 0
        archived_count = 0
        if scraped_results or (replace_current_feed and successful_platforms):
            conn = get_db_connection()
            cursor = conn.cursor()
            if replace_current_feed:
                for source_platform in answered_sources:
                    count_row = cursor.execute(
                        "SELECT COUNT(*) AS total FROM scraped_jobs WHERE platform = ? AND stale_at IS NULL AND COALESCE(status, 'Draft') IN ('Draft', 'New', '')",
                        (source_platform,),
                    ).fetchone()
                    removed_count += int(count_row["total"] if count_row else 0)
                    cursor.execute(
                        "UPDATE scraped_jobs SET stale_at = CURRENT_TIMESTAMP WHERE platform = ? AND stale_at IS NULL AND COALESCE(status, 'Draft') IN ('Draft', 'New', '')",
                        (source_platform,),
                    )
                archived_count = removed_count
            cursor.execute("SELECT id, title, company, url, platform, source_aliases_json FROM scraped_jobs")
            existing_rows = cursor.fetchall()
            known = {}
            for existing in existing_rows:
                current = dict(existing)
                for key in job_match_keys(current):
                    known[key] = current
            new_jobs = []
            for item in scraped_results:
                fingerprints = job_match_keys(item)
                existing = next((known[key] for key in fingerprints if key in known), None)
                if existing:
                    filtered["duplicates"] += 1
                    cursor.execute("UPDATE scraped_jobs SET stale_at = NULL, last_seen_at = CURRENT_TIMESTAMP WHERE id = ?", (existing["id"],))
                    try:
                        aliases = json.loads(existing.get("source_aliases_json") or "[]")
                    except (TypeError, json.JSONDecodeError):
                        aliases = []
                    alias = {"platform": item["platform"], "url": item.get("url"), "source_id": item["id"]}
                    if alias not in aliases and item["platform"] != existing.get("platform"):
                        aliases.append(alias)
                        cursor.execute("UPDATE scraped_jobs SET source_aliases_json = ? WHERE id = ?", (json.dumps(aliases), existing["id"]))
                    continue
                cursor.execute("""
                    INSERT INTO scraped_jobs (
                        id, title, company, platform, url, location, remote_type,
                        salary_range, description, posted_date, ghost_score, ghost_reasons, deadline,
                        first_seen_at, last_seen_at, stale_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL)
                    ON CONFLICT(id) DO UPDATE SET
                        title = excluded.title,
                        company = excluded.company,
                        url = excluded.url,
                        location = excluded.location,
                        remote_type = excluded.remote_type,
                        description = excluded.description,
                        posted_date = excluded.posted_date,
                        ghost_score = excluded.ghost_score,
                        ghost_reasons = excluded.ghost_reasons,
                        salary_range = excluded.salary_range,
                        deadline = excluded.deadline,
                        stale_at = NULL,
                        last_seen_at = CURRENT_TIMESTAMP
                """, (
                    item["id"], item["title"], item["company"], item["platform"],
                    item["url"], item["location"], item["remote_type"],
                    item.get("salary_range", "Not disclosed"), item.get("description", item["title"]), item.get("posted_date", "Unknown"),
                    item.get("ghost_score", 0), json.dumps(item.get("ghost_reasons", [])), item.get("deadline", "")
                ))
                for fingerprint in fingerprints:
                    known[fingerprint] = {**item, "source_aliases_json": "[]"}
                new_jobs.append(item)
            conn.commit()
            conn.close()
        
        link_checks_queued = 0
        if new_jobs:
            try:
                from backend.app.modules.scrape.job_link_health import schedule_job_link_checks

                link_checks_queued = schedule_job_link_checks([item["id"] for item in new_jobs])
            except Exception as exc:
                errors.append(f"Automatic source-link checks could not be queued: {str(exc)[:160]}")

        result_status = "partial" if errors and scraped_results else "error" if errors else "success"
        finish_scan_run(
            scan_id,
            status=result_status,
            total_scraped=len(scraped_results),
            newly_saved_count=len(new_jobs),
            removed_count=removed_count,
            errors=errors,
            raw_fetched_count=raw_fetched_count,
            filtered_count=sum(filtered[key] for key in ("low_quality", "expired", "location_mismatch", "work_mode_mismatch")),
            duplicate_count=filtered["duplicates"],
            filtered=filtered,
        )
        _record_scan_notification(len(scraped_results), errors, scan_id)
        return {
            "scan_id": scan_id,
            "status": result_status,
            "total_scraped": len(scraped_results),
            "newly_saved_count": len(new_jobs),
            "link_checks_queued": link_checks_queued,
            "successful_platforms": sorted(successful_platforms),
            "current_total": _count_current_jobs(),
            "removed_count": removed_count,
            "archived_count": archived_count,
            "raw_fetched_count": raw_fetched_count,
            "filtered_count": sum(filtered[key] for key in ("low_quality", "expired", "location_mismatch", "work_mode_mismatch")),
            "filtered": filtered,
            "jobs": scraped_results,
            "errors": errors,
            "platform_health": account_health.get_all_platform_health(),
            "source_health": get_source_health(),
        }

unified_scraper = UnifiedScraper()
