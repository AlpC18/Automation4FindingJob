"""KosovaJob is scraped directly from its public pages; no API key or Actor required."""

import httpx
import pytest

from backend.app.modules.scrape.scrapers import kosovajob_scraper as kj
from backend.app.modules.scrape.source_registry import get_source_health

LISTING = """
<div class="listCnt">
  <div class="jobListCnts jobListPrm"><a href="https://kosovajob.com/imee/agentic-ai-expert-mfd">
    <div class="jobListTitle" date="2026-11-02 23:50:00">Agentic AI Expert (m/f/d)</div>
    <div class="jobListCity">Fushë Kosovë</div></a></div>
  <div class="creativeSpaceCnt"><a href="https://ads.example.com/x">ad</a></div>
  <div class="jobListCnts jobListStd"><a href="https://kosovajob.com/tp-kosova/junior-accountant">
    <div class="jobListTitle">Junior Accountant</div><div class="jobListCity">Prishtinë</div></a></div>
  <div class="jobListCnts"><a href="https://kosovajob.com/imee/agentic-ai-expert-mfd">
    <div class="jobListTitle">Agentic AI Expert (m/f/d)</div></a></div>
  <div class="jobListCnts"><a href="https://evil.example.com/a/b"><div class="jobListTitle">Off-site</div></a></div>
  <div class="jobListCnts"><a href="https://kosovajob.com/blog"><div class="jobListTitle">Not a job</div></a></div>
</div>"""
DETAIL = """
<html><head><meta property="og:description" content="Build agents in Copilot Studio.&#10;Python is a plus."/></head>
<body><h1>Agentic AI Expert (m/f/d)</h1><b class="containerLeftAreaTopAreaRightTitleComp">IMEE</b>
<span class="tagCnt">IT</span><span class="tagCnt">Python</span><span class="tagCnt">IT</span></body></html>"""


def test_listing_keeps_only_unique_on_site_job_pages():
    assert kj.parse_listing(LISTING) == [
        {"title": "Agentic AI Expert (m/f/d)", "url": "https://kosovajob.com/imee/agentic-ai-expert-mfd", "company": "Imee", "location": "Fushë Kosovë, Kosovo", "deadline": "2026-11-02 23:50:00"},
        {"title": "Junior Accountant", "url": "https://kosovajob.com/tp-kosova/junior-accountant", "company": "Tp Kosova", "location": "Prishtinë, Kosovo", "deadline": ""},
    ]


def test_detail_page_supplies_company_description_and_tags():
    assert kj.parse_detail(DETAIL) == {
        "company": "IMEE", "description": "Build agents in Copilot Studio.\nPython is a plus.", "tags": ["IT", "Python"],
    }
    assert kj.parse_detail("<html></html>") == {}


@pytest.fixture
def site(monkeypatch):
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/":
            return httpx.Response(200, text=LISTING)
        if "junior-accountant" in request.url.path:
            return httpx.Response(500)
        return httpx.Response(200, text=DETAIL)

    real_client = httpx.Client
    monkeypatch.setattr(kj.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr(kj.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(kj, "robots_allows", lambda url: True)
    monkeypatch.setattr(kj, "get_source_config", lambda source: {"has_custom_config": False, "actor_id": ""})
    return requested


def test_scan_searches_the_site_and_enriches_jobs_from_their_pages(site):
    jobs = kj.KosovaJobScraper().fetch_jobs("python")

    assert site[0] == "https://kosovajob.com/?q=python"
    assert [job["platform"] for job in jobs] == ["kosovajob", "kosovajob"]
    assert jobs[0]["company"] == "IMEE" and jobs[0]["source_tags"] == ["IT", "Python"]
    assert jobs[0]["deadline"] == "2026-11-02" and jobs[1]["deadline"] == ""
    assert jobs[0]["description"].startswith("Build agents in Copilot Studio.")
    # The broken detail page falls back to what the listing showed instead of dropping the job.
    assert jobs[1]["title"] == "Junior Accountant" and jobs[1]["company"] == "Tp Kosova"


def test_location_preference_filters_before_any_detail_request(site):
    jobs = kj.KosovaJobScraper().fetch_jobs("python", location="Prishtinë")
    assert [job["title"] for job in jobs] == ["Junior Accountant"]
    assert len(site) == 2
    assert len(kj.KosovaJobScraper().fetch_jobs("python", location="Kosovo")) == 2


def test_configured_apify_actor_takes_precedence(site, monkeypatch):
    monkeypatch.setattr(kj, "get_source_config", lambda source: {"has_custom_config": True, "actor_id": "acme/kosovajob"})
    monkeypatch.setattr(kj.apify_job_source, "fetch", lambda *args: [{"via": "apify", "args": args}])
    assert kj.KosovaJobScraper().fetch_jobs("python", "Prishtinë") == [{"via": "apify", "args": ("kosovajob", "python", "Prishtinë")}]
    assert site == []
