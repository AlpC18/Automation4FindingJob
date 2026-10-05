"""Execute a saved role search, rank its results and persist actionable alerts."""

import asyncio
import json
import uuid

from backend.app.api.profile import fetch_candidate_profile
from backend.app.core.database import get_db_connection
from backend.app.modules.rank.llm_reranker import review_top_jobs
from backend.app.modules.rank.scoring_engine import rank_and_save_all_jobs
from backend.app.modules.scrape.unified_scraper import unified_scraper


def run_saved_search(search_id: str) -> dict:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM saved_searches WHERE id = ?", (search_id,))
        saved = cursor.fetchone()
        if not saved:
            raise ValueError("Saved search not found")
        cursor.execute("SELECT id FROM scraped_jobs WHERE stale_at IS NULL")
        before = {row["id"] for row in cursor.fetchall()}
    finally:
        conn.close()

    # Saved searches are additive: each saved role contributes to the shared
    # feed instead of deleting the previous role's current results.
    scrape = unified_scraper.run_multi_platform_scrape(
        queries=json.loads(saved["queries_json"]),
        location_preference=saved["location"] or None,
        remote_type=(saved["remote_type"] if "remote_type" in saved.keys() else "") or None,
        replace_current_feed=False,
    )
    profile = fetch_candidate_profile()
    ranked = rank_and_save_all_jobs(profile)
    provider = saved["llm_provider"] if "llm_provider" in saved.keys() else ""
    if provider:
        # Runs in a worker thread, so it owns its event loop. The review never raises.
        asyncio.run(review_top_jobs(profile, provider=provider))
        # The review replaced some rule scores; alerts below must use what is now stored.
        conn = get_db_connection()
        try:
            stored = {row["id"]: row["match_score"] for row in conn.cursor().execute("SELECT id, match_score FROM scraped_jobs WHERE stale_at IS NULL").fetchall()}
        finally:
            conn.close()
        ranked = [{**job, "match_score": stored.get(job["id"], job.get("match_score", 0)) or 0} for job in ranked]
    matches = [job for job in ranked if job["id"] not in before and job.get("match_score", 0) >= saved["min_match_score"]]
    conn = get_db_connection()
    try:
        if matches:
            conn.cursor().execute("INSERT INTO user_notifications(id, title, body, href) VALUES (?, ?, ?, ?)",
                (uuid.uuid4().hex, f"{saved['name']}: yeni uygun ilanlar", f"{len(matches)} yeni ilan eşleşti; en yüksek puan %{max(job['match_score'] for job in matches):.0f}.", "/jobs"))
            conn.commit()
        return {"search": saved["name"], "new_matches": len(matches), "jobs": matches[:20], "scrape": scrape}
    finally:
        conn.close()


def run_enabled_saved_searches() -> list[dict]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM saved_searches WHERE enabled = 1 ORDER BY created_at")
        search_ids = [row["id"] for row in cursor.fetchall()]
    finally:
        conn.close()
    results = []
    for search_id in search_ids:
        try:
            results.append(run_saved_search(search_id))
        except Exception as exc:
            results.append({"search_id": search_id, "error": str(exc)[:240]})
    return results
