"""Techcareer.net is read from the JSON its public pages embed; no API key required."""

import json

import httpx
import pytest

from backend.app.modules.scrape.scrapers import techcareer_scraper as tc


def _page(page_props):
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps({"props": {"pageProps": page_props}})}</script></html>'


def _list_page(items, page_count=2):
    return _page({"initialJobList": {"jobListItems": items, "pagination": {"page": 1, "pageCount": page_count}}})


PAGE_1 = _list_page([
    {"id": 1, "title": "Kıdemli Yazılım Geliştirici", "jobTitleEn": "Senior Software Developer", "slug": "yazilim-1", "workPlaces": ["Uzaktan"],
     "location": "İstanbul(Avr.) / Türkiye", "owner": {"name": "Acme Yazılım"}},
    {"id": 2, "title": "Dijital Pazarlama Uzmanı", "jobTitleEn": "Digital Marketing Specialist", "slug": "pazarlama-2", "workPlaces": ["İş Yerinde"], "location": "Ankara / Türkiye", "owner": {"name": "X"}},
    {"id": 3, "title": "Closed Developer", "slug": "closed-3", "isDisabledJob": True, "owner": {}},
])
PAGE_2 = _list_page([
    {"id": 4, "title": "Backend Developer", "slug": "backend-4", "isCompanyHidden": True, "hiddenCompanyInfo": "Gizli Firma",
     "workPlaces": ["Hibrit"], "location": "Ankara / Türkiye", "owner": {"name": ""}},
])
DETAIL = _page({"jobDetail": {
    "head": {"startDate": "2026-10-05T00:00:00.000Z", "endDate": "2026-11-03T00:00:00.000Z"},
    "content": {"description": "<p>Java ve Spring Boot ile servis geliştirme.</p>", "skills": ["Java", "Spring Boot"]},
}})


def test_listing_reads_open_jobs_and_page_count():
    listing = tc.parse_listing(PAGE_1)
    assert listing["page_count"] == 2
    assert listing["jobs"][0] == {
        "id": "techcareer-1", "title": "Kıdemli Yazılım Geliştirici", "title_en": "Senior Software Developer",
        "company": "Acme Yazılım", "url": "https://www.techcareer.net/jobs/detail/yazilim-1",
        "location": "İstanbul(Avr.) / Türkiye", "workplace_type": "Remote",
    }
    assert [job["id"] for job in listing["jobs"]] == ["techcareer-1", "techcareer-2"]
    assert listing["jobs"][1]["workplace_type"] == "Onsite"
    assert tc.parse_listing("<html>layout changed</html>") == {"jobs": [], "page_count": 1}


def test_detail_supplies_description_skills_and_dates():
    assert tc.parse_detail(DETAIL) == {
        "description": "<p>Java ve Spring Boot ile servis geliştirme.</p>", "tags": ["Java", "Spring Boot"],
        "date": "2026-10-05T00:00:00.000Z", "deadline": "2026-11-03T00:00:00.000Z",
    }
    assert tc.parse_detail("<html></html>") == {}


def test_query_matches_either_language_and_ignores_seniority_words():
    job = {"title": "Kıdemli Yazılım Geliştirici", "title_en": "Senior Software Developer"}
    assert tc.matches_query(job, "Junior Software Developer")
    assert tc.matches_query(job, "yazılım")
    assert not tc.matches_query(job, "Senior Marketing")
    assert tc.matches_query(job, "")


@pytest.fixture
def site(monkeypatch):
    requested, state = [], {"empty": False}

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/jobs/detail/unknown":
            return httpx.Response(404)
        if request.url.path == "/jobs":
            if state["empty"]:
                return httpx.Response(200, text="<html>redesigned</html>")
            return httpx.Response(200, text=PAGE_2 if request.url.params.get("jobs[page]") == "2" else PAGE_1)
        if request.url.path.endswith("backend-4"):
            return httpx.Response(500)
        return httpx.Response(200, text=DETAIL)

    real_client = httpx.Client
    monkeypatch.setattr(tc.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr(tc.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(tc, "robots_allows", lambda url: True)
    return requested, state


def test_scan_walks_every_list_page_and_enriches_matching_jobs(site):
    requested, _ = site
    jobs = tc.TechcareerScraper().fetch_jobs("developer")

    assert sum("/jobs?" in url for url in requested) == 2
    assert not any("pazarlama" in url for url in requested)
    assert [job["title"] for job in jobs] == ["Kıdemli Yazılım Geliştirici", "Backend Developer"]
    first, second = jobs
    assert first["platform"] == "techcareer" and first["remote_type"] == "Remote"
    assert first["description"] == "Java ve Spring Boot ile servis geliştirme."
    assert first["deadline"] == "2026-11-03" and first["source_tags"] == ["Java", "Spring Boot"]
    # Hidden employer and a failing detail page: the listing-level record is still kept.
    assert second["company"] == "Gizli Firma" and second["remote_type"] == "Hybrid" and second["deadline"] == ""


def test_location_filter_and_layout_change(site):
    _, state = site
    assert [job["title"] for job in tc.TechcareerScraper().fetch_jobs("developer", location="Ankara")] == ["Backend Developer"]
    state["empty"] = True
    with pytest.raises(RuntimeError, match="layout may have changed"):
        tc.TechcareerScraper().fetch_jobs("developer")


def test_a_second_query_in_the_same_scan_reuses_the_listing_and_details(site):
    requested, _ = site
    scraper = tc.TechcareerScraper()
    scraper.fetch_jobs("developer")
    first_scan = len(requested)
    assert [job["title"] for job in scraper.fetch_jobs("backend")] == ["Backend Developer"]
    # Only the detail page that failed before is retried; the two list pages are not read again.
    assert requested[first_scan:] == ["https://www.techcareer.net/jobs/detail/backend-4"]
