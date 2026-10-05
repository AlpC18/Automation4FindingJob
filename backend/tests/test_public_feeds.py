"""Key-free feeds and company career boards: provider payloads become normalized jobs."""

import httpx
import pytest

from backend.app.modules.scrape import live_sources, public_feeds
from backend.app.modules.scrape import unified_scraper as us

PAYLOADS = {
    "remoteok.test": [{"legal": "notice"}, {"id": 1, "position": "Python Engineer", "company": "Rok", "url": "https://remoteok.test/1", "description": "Python APIs"}],
    "arbeitnow.test": {"data": [{"slug": "a", "title": "Python Dev", "company_name": "Arb", "url": "https://arbeitnow.test/a", "description": "python", "location": "Berlin", "remote": True}]},
    "remotive.com": {"jobs": [{"id": 2, "title": "Python Backend", "company_name": "Rem", "url": "https://remotive.com/2", "description": "<p>Django</p>", "candidate_required_location": "Worldwide", "salary": "$90k", "publication_date": "2026-10-02T20:01:00"}]},
    "jobicy.com": {"jobs": [
        {"id": 3, "jobTitle": "Python Data Engineer", "companyName": "Job", "url": "https://jobicy.com/3", "jobDescription": "ETL", "jobGeo": "Europe", "pubDate": "2026-10-04T05:45:40+00:00", "salaryMin": None, "jobIndustry": ["Data"]},
        {"id": 4, "jobTitle": "Copywriter", "companyName": "Job", "url": "https://jobicy.com/4", "jobDescription": "words", "jobGeo": "USA"},
    ]},
    "himalayas.app": {"jobs": [{"title": "Senior Python Developer", "companyName": "Him", "applicationLink": "https://himalayas.app/j/5", "excerpt": "apis", "locationRestrictions": ["Albania", "Kosovo"], "pubDate": 1790075996, "minSalary": 50000, "maxSalary": 70000, "currency": "USD"}]},
    "boards-api.greenhouse.io": {"jobs": [{"id": 6, "title": "Python Platform Engineer", "company_name": "Stripe", "absolute_url": "https://stripe.com/jobs/6", "content": "&lt;p&gt;Build &amp;amp; run&lt;/p&gt;", "location": {"name": "Dublin"}, "first_published": "2026-09-03T13:32:53-04:00"}]},
    "api.lever.co": [{"id": "7", "text": "Python SRE", "hostedUrl": "https://jobs.lever.co/acme-labs/7", "descriptionPlain": "on call", "categories": {"location": "Stockholm"}, "workplaceType": "hybrid", "createdAt": 1782214185805}],
    "api.ashbyhq.com": {"jobs": [
        {"id": "8", "title": "Python Security Engineer", "jobUrl": "https://jobs.ashbyhq.com/ramp/8", "descriptionPlain": "appsec", "location": "New York", "isRemote": True, "publishedAt": "2026-04-07T17:12:35+00:00"},
        {"id": "9", "title": "Python Hidden Role", "jobUrl": "https://jobs.ashbyhq.com/ramp/9", "isListed": False},
    ]},
}


@pytest.fixture
def fake_network(monkeypatch):
    requested, down = [], set()

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.host in down:
            return httpx.Response(503)
        return httpx.Response(200, json=PAYLOADS[request.url.host])

    real_client = httpx.Client
    monkeypatch.setattr(live_sources.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr(live_sources.settings, "REMOTEOK_API_URL", "https://remoteok.test/api")
    monkeypatch.setattr(live_sources.settings, "ARBEITNOW_API_URL", "https://arbeitnow.test/api")
    return requested, down


def test_every_public_feed_is_read_and_normalized(fake_network):
    requested, _ = fake_network
    source = live_sources.PublicRemoteJobSources()
    jobs = {job["platform"]: job for job in source.fetch("python")}

    assert set(jobs) == source.answered == {"remoteok", "arbeitnow", "remotive", "jobicy", "himalayas"}
    assert any("remotive.com/api/remote-jobs?search=python" in url for url in requested)
    assert jobs["remotive"]["description"] == "Django" and jobs["remotive"]["salary_range"] == "$90k"
    assert jobs["jobicy"]["title"] == "Python Data Engineer" and jobs["jobicy"]["location"] == "Europe"
    assert jobs["jobicy"]["salary_range"] == "Not disclosed" and jobs["jobicy"]["remote_type"] == "Remote"
    assert jobs["himalayas"]["location"] == "Albania, Kosovo"
    assert jobs["himalayas"]["salary_range"] == "50000 - 70000 USD"
    assert jobs["himalayas"]["posted_date"].startswith("2026-")


def test_one_feed_being_down_does_not_fail_the_scan_or_claim_it_answered(fake_network):
    _, down = fake_network
    down.add("remotive.com")
    source = live_sources.PublicRemoteJobSources()
    assert "remotive" not in {job["platform"] for job in source.fetch("python")}
    assert "remotive" not in source.answered and "jobicy" in source.answered


def test_all_feeds_down_is_an_error(fake_network):
    _, down = fake_network
    down.update(PAYLOADS)
    with pytest.raises(RuntimeError, match="remoteok"):
        live_sources.PublicRemoteJobSources().fetch("python")


def test_company_boards_read_greenhouse_lever_and_ashby(fake_network, monkeypatch):
    requested, _ = fake_network
    monkeypatch.setattr(live_sources, "list_company_boards", lambda: [
        {"provider": "greenhouse", "slug": "stripe"}, {"provider": "lever", "slug": "acme-labs"}, {"provider": "ashby", "slug": "ramp"},
    ])
    source = live_sources.CompanyBoardJobSources()
    jobs = {job["platform"]: job for job in source.fetch("python")}

    assert set(jobs) == source.answered == {"greenhouse", "lever", "ashby"}
    assert "https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true" in requested
    assert jobs["greenhouse"]["company"] == "Stripe" and jobs["greenhouse"]["location"] == "Dublin"
    assert jobs["greenhouse"]["description"] == "Build &amp; run"
    assert jobs["lever"]["company"] == "Acme Labs" and jobs["lever"]["remote_type"] == "hybrid"
    assert jobs["lever"]["posted_date"].startswith("2026-")
    assert jobs["ashby"]["title"] == "Python Security Engineer" and jobs["ashby"]["remote_type"] == "Remote"
    assert source.fetch("python", location="Dublin") == [jobs["greenhouse"]]


def test_company_boards_need_configuration(monkeypatch):
    monkeypatch.setattr(live_sources, "list_company_boards", lambda: [])
    with pytest.raises(RuntimeError, match="COMPANY_BOARDS"):
        live_sources.CompanyBoardJobSources().fetch("python")


@pytest.mark.parametrize("raw", ["workday:acme", "greenhouse:", "lever:../admin", "ashby:a/b", "stripe"])
def test_invalid_company_board_entries_are_rejected(raw):
    with pytest.raises(ValueError, match="COMPANY_BOARDS"):
        public_feeds.parse_company_boards(raw)


def test_company_boards_are_parsed_and_deduplicated():
    assert public_feeds.parse_company_boards(" Greenhouse:Stripe ,lever:spotify,,greenhouse:stripe") == [
        ("greenhouse", "stripe"), ("lever", "spotify"),
    ]


def test_configured_company_boards_join_the_default_scan(monkeypatch):
    blank = {"has_custom_config": False, "enabled": True, "actor_id": ""}
    monkeypatch.setattr(us, "get_source_config", lambda source: blank)
    monkeypatch.setattr(us.settings, "SCRAPER_PLATFORMS", "remote")
    monkeypatch.setattr(us, "list_company_boards", lambda: [])
    assert us._default_platforms([]) == ["remote"]
    monkeypatch.setattr(us, "list_company_boards", lambda: [{"provider": "ashby", "slug": "ramp"}])
    assert us._default_platforms([]) == ["remote", "company_boards"]
    assert "company_boards" in us.UnifiedScraper().scrapers


@pytest.mark.parametrize("text, expected", [
    ("greenhouse:stripe", ("greenhouse", "stripe")),
    ("https://boards.greenhouse.io/stripe/jobs/123", ("greenhouse", "stripe")),
    ("https://job-boards.greenhouse.io/Stripe", ("greenhouse", "stripe")),
    ("https://jobs.lever.co/spotify", ("lever", "spotify")),
    ("https://jobs.ashbyhq.com/ramp/abc", ("ashby", "ramp")),
])
def test_board_reference_accepts_short_form_and_careers_urls(text, expected):
    assert public_feeds.parse_board_reference(text) == expected


@pytest.mark.parametrize("text", ["https://stripe.com/jobs", "https://jobs.lever.co/", "workday:acme", "greenhouse:a,lever:b", ""])
def test_unusable_board_references_are_rejected(text):
    with pytest.raises(ValueError):
        public_feeds.parse_board_reference(text)


def test_company_board_api_verifies_saves_lists_and_removes(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.app.api.routers import scrape as scrape_router
    from backend.app.main import app

    client = TestClient(app)
    checked = []

    def verify(provider, slug):
        checked.append((provider, slug))
        if slug == "ghost":
            raise ValueError("lever üzerinde 'ghost' adında bir kariyer sayfası bulunamadı.")
        return 12

    monkeypatch.setattr(scrape_router.company_board_job_sources, "verify", verify)
    monkeypatch.setattr(scrape_router.settings, "COMPANY_BOARDS", "ashby:ramp")

    missing = client.post("/api/scrape/company-boards", json={"board": "lever:ghost"})
    assert missing.status_code == 422 and "bulunamadı" in missing.json()["detail"]
    assert client.post("/api/scrape/company-boards", json={"board": "https://example.com/careers"}).status_code == 422

    saved = client.post("/api/scrape/company-boards", json={"board": "https://jobs.lever.co/spotify"})
    assert saved.status_code == 200 and saved.json()["open_jobs"] == 12
    assert checked[-1] == ("lever", "spotify")
    boards = client.get("/api/scrape/company-boards").json()
    assert {"provider": "ashby", "slug": "ramp", "origin": "env"} in boards["boards"]
    assert {"provider": "lever", "slug": "spotify", "origin": "saved"} in boards["boards"]
    assert boards["providers"] == ["greenhouse", "lever", "ashby"]

    remaining = client.delete("/api/scrape/company-boards/lever/spotify").json()["boards"]
    assert remaining == [{"provider": "ashby", "slug": "ramp", "origin": "env"}]
