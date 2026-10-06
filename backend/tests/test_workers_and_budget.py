"""Worker-process tasks and the Apify spending guard."""

import httpx
import pytest

from backend.app.modules.scrape import apify_budget as budget
from backend.app.tasks import worker_tasks as tasks
from backend.app.tasks.job_store import create_job, get_job


def test_worker_scan_updates_its_job_record(monkeypatch):
    from backend.app.modules.scrape.unified_scraper import unified_scraper
    asked = {}

    def scrape(**options):
        asked.update(options)
        return {"jobs": [{}], "saved_jobs": [{"id": "j1"}], "total_scraped": 4, "scan_id": "s1"}

    monkeypatch.setattr(unified_scraper, "run_multi_platform_scrape", scrape)
    job, _ = create_job("scrape", {"keywords": "backend"}, "worker-test-scan")

    result = tasks.task_scrape_jobs.apply(kwargs={"keywords": "backend", "location": "Remote", "job_id": job["id"]}).get()

    assert (result["status"], result["job_ids"], result["total_scraped"]) == ("SUCCESS", ["j1"], 4)
    assert (asked["query"], asked["location_preference"]) == ("backend", "Remote")
    assert get_job(job["id"])["status"] == "succeeded"


def test_worker_ranking_link_checks_and_browser_task_run(monkeypatch):
    from backend.app.modules.scrape import job_link_health
    checked = []
    monkeypatch.setattr(job_link_health, "_run_checks", lambda job_ids, tenant_id: checked.append(job_ids))

    ranked = tasks.task_rank_all_jobs.apply().get()
    links = tasks.task_check_job_links.apply(kwargs={"job_ids": ["a", "b"]}).get()
    browser = tasks.task_stealth_apply.apply(kwargs={"job_id": "missing", "applicant_data": {}}).get()

    assert ranked["status"] == "SUCCESS" and ranked["processed_count"] >= 0
    assert links == {"status": "SUCCESS", "checked_count": 2} and checked == [["a", "b"]]
    assert browser["status"] == "DISABLED"  # the fallback URL is LinkedIn, and LinkedIn automation is opt-in


def test_worker_email_sync_returns_the_agents_result(monkeypatch):
    from backend.app.modules.outcome.oauth_mail_agent import oauth_mail_agent

    async def sync(provider=None):
        return {"status": "success", "synced": 0}

    monkeypatch.setattr(oauth_mail_agent, "sync_emails", sync)

    assert tasks.task_sync_emails.apply().get()["synced"] == 0


def _apify(monkeypatch, accounts):
    """accounts: token -> (account id, used USD) or an HTTP error code."""
    def handler(request: httpx.Request) -> httpx.Response:
        token = request.headers["Authorization"].removeprefix("Bearer ")
        account = accounts[token]
        if isinstance(account, int):
            return httpx.Response(account, json={})
        if request.url.path.endswith("/usage/monthly"):
            return httpx.Response(200, json={"data": {"totalUsageCreditsUsdAfterVolumeDiscount": account[1], "usageCycle": {"startAt": "2026-10-01", "endAt": "2026-10-31"}}})
        return httpx.Response(200, json={"data": {"id": account[0]}})

    real_client = httpx.Client
    monkeypatch.setattr(budget.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr(budget, "apify_tokens", lambda source: list(accounts))
    monkeypatch.setattr(budget, "_cache", {})
    monkeypatch.setattr(budget, "_last_scan", {})


def test_quota_counts_each_account_once_and_flags_bad_keys(monkeypatch):
    _apify(monkeypatch, {"key-one-aaaa": ("acct-1", 1.5), "key-two-bbbb": ("acct-1", 1.5), "key-bad-cccc": 401})

    summary = budget.get_apify_quota_summary("linkedin")

    assert (summary["configured_keys"], summary["valid_keys"], summary["invalid_keys"], summary["distinct_accounts"]) == (3, 2, 1, 1)
    assert (summary["budget_usd"], summary["used_usd"], summary["remaining_usd"], summary["percent_used"]) == (5.0, 1.5, 3.5, 30.0)
    assert all("account_id" not in account and account["masked"].startswith("••••") for account in summary["accounts"])
    assert summary["last_scan_cost_usd"] is None


def test_a_scan_is_charged_to_the_first_account_with_headroom(monkeypatch):
    _apify(monkeypatch, {"key-spent-aaaa": ("acct-1", 5.0), "key-fresh-bbbb": ("acct-2", 4.4)})

    token, allowance = budget.select_apify_account("linkedin", max_charge_usd=2.0)

    assert token == "key-fresh-bbbb" and allowance == pytest.approx(0.6)
    budget.mark_scan_start()
    assert budget.get_apify_quota_summary("linkedin", force_refresh=True)["last_scan_cost_usd"] == 0.0
    budget.invalidate_apify_token_usage("key-fresh-bbbb")
    assert budget._fingerprint("key-fresh-bbbb") not in budget._cache


def test_scans_are_refused_when_no_verified_account_has_budget_left(monkeypatch):
    _apify(monkeypatch, {"key-spent-aaaa": ("acct-1", 9.0), "key-bad-cccc": 500})
    with pytest.raises(RuntimeError, match="doğrulanmış"):
        budget.select_apify_account("linkedin", 1.0)

    _apify(monkeypatch, {})
    with pytest.raises(RuntimeError, match="ayarlanmamış"):
        budget.select_apify_account("linkedin", 1.0)


def test_an_unreachable_apify_counts_as_an_invalid_key(monkeypatch):
    def offline(**kwargs):
        raise httpx.ConnectError("offline")

    _apify(monkeypatch, {"key-one-aaaa": ("acct-1", 0)})
    monkeypatch.setattr(budget.httpx, "Client", offline)

    assert budget.get_apify_quota_summary("linkedin")["valid_keys"] == 0
