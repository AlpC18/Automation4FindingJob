"""The built-in Apify scrapers get the input they expect and their nested output is readable."""

from backend.app.modules.scrape import source_registry
from backend.app.modules.scrape.live_sources import _apply_search_area, _decode_actor_input, _title_matches, normalize_job


def test_each_known_actor_receives_the_search_text_under_its_own_input_key():
    assert _decode_actor_input('{"country":"us"}', "python", "Berlin", "valig/indeed-jobs-scraper") == {
        "country": "us", "title": "python", "limit": 100, "location": "Berlin",
    }
    assert _decode_actor_input("{}", "python", None, "blackfalcondata/kariyer-scraper") == {"query": "python", "maxResults": 100}
    # Upwork's "location" is a list of client regions, so a free-text location must not be sent.
    assert "location" not in _decode_actor_input("{}", "python", "Berlin", "neatrat/upwork-job-scraper")


def test_unknown_actors_keep_the_generic_query_keys():
    payload = _decode_actor_input("{}", "python", None, "someone/custom-actor")
    assert payload == {"query": "python", "searchQuery": "python", "keyword": "python"}


def test_nested_indeed_and_glassdoor_records_are_normalized():
    indeed = normalize_job({
        "key": "5e5d", "title": "Quant Analyst", "url": "https://www.indeed.com/viewjob?jk=5e5d",
        "employer": {"name": "Citi"}, "location": {"countryName": "United States", "city": "New York"},
        "description": {"text": "Build models.", "html": "<p>Build models.</p>"}, "datePublished": "2025-06-04T05:00:00.000Z",
    }, "indeed")
    assert (indeed["company"], indeed["location"], indeed["description"]) == ("Citi", "New York, United States", "Build models.")
    assert indeed["posted_date"] == "2025-06-04T05:00:00.000Z"

    glassdoor = normalize_job({
        "id": 101, "title": "Senior Engineer", "url": "https://www.glassdoor.com/job-listing/j?jl=101",
        "employer": {"id": 1, "name": "Acme"}, "location": {"name": "Austin, TX"}, "description": "<div>Java</div>",
    }, "glassdoor")
    assert (glassdoor["company"], glassdoor["location"], glassdoor["description"]) == ("Acme", "Austin, TX", "Java")


def test_upwork_records_keep_budget_date_and_client_location():
    job = normalize_job({
        "id": "21", "title": "Django API", "url": "https://www.upwork.com/jobs/x", "description": "Finish the backend.",
        "budget": "$600.00", "absoluteDate": "2026-10-05T13:26:37.410Z", "clientLocation": "Australia", "tags": ["Python"],
    }, "upwork")
    assert (job["salary_range"], job["posted_date"], job["location"]) == ("$600.00", "2026-10-05T13:26:37.410Z", "Australia")


def test_a_source_without_its_own_token_reuses_one_saved_for_another_source(monkeypatch):
    saved = {"linkedin": ["linkedin-token"]}
    monkeypatch.setattr(source_registry, "get_source_config", lambda source: {"api_tokens": saved.get(source, [])})
    monkeypatch.setattr(source_registry.settings, "APIFY_API_TOKEN", "")
    assert source_registry.apify_tokens("indeed") == ["linkedin-token"]
    assert source_registry.apify_tokens("linkedin") == ["linkedin-token"]
    saved.clear()
    assert source_registry.apify_tokens("indeed") == []


def test_a_country_search_selects_indeeds_country_and_remote_becomes_its_location():
    payload = {"country": "us", "location": "Germany"}
    assert _apply_search_area("valig/indeed-jobs-scraper", payload, "Germany", remote=True) is True
    assert payload == {"country": "de", "location": "Remote"}

    payload = {"country": "us", "location": "Germany"}
    assert _apply_search_area("valig/indeed-jobs-scraper", payload, "Germany", remote=False) is False
    assert payload == {"country": "de"}

    payload = {"location": "United States"}
    assert _apply_search_area("valig/glassdoor-jobs-scraper", payload, "United Kingdom", remote=True) is True
    assert payload == {"location": "United Kingdom", "remoteWorkType": True}

    payload = {}
    assert _apply_search_area("neatrat/upwork-job-scraper", payload, "Germany", remote=True) is False
    assert payload == {}


def test_actor_results_are_kept_by_headline_not_by_a_word_in_the_description():
    dental = {"title": "Diş Hekimi Asistanı", "description": "Klinik yazılım kullanabilen", "source_tags": []}
    engineer = {"title": "Lead Software Engineer", "description": "Build services.", "source_tags": []}
    tagged = {"title": "Backend Engineer", "description": "", "source_tags": ["Python"]}
    assert not _title_matches(dental, "yazılım")
    assert _title_matches(engineer, "software developer")
    assert _title_matches(tagged, "python developer")


def test_last_scan_cost_is_the_spend_since_the_scan_started(monkeypatch):
    from backend.app.modules.scrape import apify_budget

    used = {"usd": 0.25}
    monkeypatch.setattr(apify_budget, "apify_tokens", lambda source: ["token"])
    monkeypatch.setattr(apify_budget, "_fetch_status", lambda token, slot: {"valid": True, "account_id": "a", "used_usd": used["usd"], "slot": slot})
    monkeypatch.setattr(apify_budget, "_last_scan", {})

    assert apify_budget.get_apify_quota_summary()["last_scan_cost_usd"] is None
    apify_budget.mark_scan_start()
    used["usd"] = 0.31
    summary = apify_budget.get_apify_quota_summary()
    assert summary["last_scan_cost_usd"] == 0.06
    assert summary["remaining_usd"] == 4.69
