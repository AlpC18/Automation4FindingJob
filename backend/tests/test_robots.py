"""Page scrapers read a site's robots.txt first and stay out of what it disallows."""

import httpx
import pytest

from backend.app.modules.scrape import robots
from backend.app.modules.scrape.scrapers import kosovajob_scraper


@pytest.fixture
def site(monkeypatch):
    def serve(status=200, body="", error=None):
        robots._rules.cache_clear()

        def fake_get(url, **kwargs):
            if error:
                raise error
            return httpx.Response(status, text=body, request=httpx.Request("GET", url))

        monkeypatch.setattr(robots.httpx, "get", fake_get)
    yield serve
    robots._rules.cache_clear()


def test_disallowed_paths_are_refused_and_the_rest_allowed(site):
    site(body="User-agent: *\nDisallow: /private/\n")

    assert robots.robots_allows("https://jobs.test/listing") is True
    assert robots.robots_allows("https://jobs.test/private/job-1") is False


def test_rules_addressed_to_our_agent_win_over_the_wildcard(site):
    site(body="User-agent: AutonomousCareerAgent\nDisallow: /\n\nUser-agent: *\nAllow: /\n")

    assert robots.robots_allows("https://jobs.test/listing") is False


def test_no_robots_file_allows_and_an_unreadable_one_refuses(site):
    site(status=404)
    assert robots.robots_allows("https://jobs.test/listing") is True
    site(status=503)
    assert robots.robots_allows("https://jobs.test/listing") is False
    site(error=httpx.ConnectError("down"))
    assert robots.robots_allows("https://jobs.test/listing") is False


def test_the_file_is_read_once_per_site(site, monkeypatch):
    site(body="User-agent: *\nDisallow:\n")
    calls = []
    original = robots.httpx.get
    monkeypatch.setattr(robots.httpx, "get", lambda url, **kwargs: calls.append(url) or original(url, **kwargs))

    robots.robots_allows("https://jobs.test/a")
    robots.robots_allows("https://jobs.test/b")

    assert calls == ["https://jobs.test/robots.txt"]


def test_a_scraper_does_not_read_a_list_the_site_disallows(monkeypatch):
    monkeypatch.setattr(kosovajob_scraper, "robots_allows", lambda url: False)

    with pytest.raises(RuntimeError, match="robots.txt"):
        kosovajob_scraper.KosovaJobScraper()._scrape("developer", None)
