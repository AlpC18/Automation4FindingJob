"""Spec section 1.2: every listed portal is a configurable, scannable source."""

from backend.app.modules.scrape import unified_scraper as us
from backend.app.modules.scrape.portal_health import PORTAL_DOMAINS
from backend.app.modules.scrape.source_registry import ACTOR_SOURCES

SPEC_PORTALS = {
    "linkedin", "upwork", "fiverr", "freelancer", "toptal", "kosovajob",
    "gjirafawork", "kariyernet", "indeed", "glassdoor", "wellfound",
}


def test_every_spec_portal_is_registered():
    assert SPEC_PORTALS <= set(ACTOR_SOURCES)
    assert SPEC_PORTALS | {"remote"} <= set(us.UnifiedScraper().scrapers)
    assert SPEC_PORTALS <= set(PORTAL_DOMAINS)


def test_portal_adapter_delegates_to_its_apify_actor(monkeypatch):
    calls = []
    monkeypatch.setattr(us.apify_job_source, "fetch", lambda *args: calls.append(args) or [])
    assert us.UnifiedScraper().scrapers["indeed"].fetch_jobs(query="Backend", location="Remote") == []
    assert calls == [("indeed", "Backend", "Remote")]


def test_default_scan_adds_only_sources_enabled_in_settings(monkeypatch):
    configs = {
        "indeed": {"has_custom_config": True, "enabled": True, "actor_id": "acme/indeed"},
        "glassdoor": {"has_custom_config": True, "enabled": False, "actor_id": "acme/glassdoor"},
    }
    blank = {"has_custom_config": False, "enabled": True, "actor_id": ""}
    monkeypatch.setattr(us, "get_source_config", lambda source: configs.get(source, blank))
    monkeypatch.setattr(us.settings, "SCRAPER_PLATFORMS", "linkedin,remote")
    assert us._default_platforms(["linkedin"]) == ["linkedin", "remote", "indeed"]
