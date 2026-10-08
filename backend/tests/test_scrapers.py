from backend.app.modules.scrape.unified_scraper import unified_scraper
from backend.app.modules.scrape.scrapers.linkedin_scraper import LinkedInScraper
from backend.app.modules.scrape.scrapers.kosovajob_scraper import KosovaJobScraper
from backend.app.modules.scrape.scrapers.techcareer_scraper import TechcareerScraper
from backend.app.modules.scrape.scrapers.upwork_scraper import UpworkScraper
from backend.app.modules.scrape.scrapers.remote_scraper import GlobalRemoteScraper


def test_unified_scraper_has_registry():
    """Verify UnifiedScraper has all expected scrapers registered."""
    assert hasattr(unified_scraper, "scrapers")
    registered_platforms = set(unified_scraper.scrapers.keys())
    expected = {"linkedin", "kosovajob", "techcareer", "upwork", "remote"}
    assert expected.issubset(registered_platforms)


def test_scraper_instances():
    """Verify scraper instances can be instantiated and have required methods."""
    li = LinkedInScraper()
    assert hasattr(li, "fetch_jobs") or hasattr(li, "scrape")
    assert li.platform_name == "linkedin"

    kj = KosovaJobScraper()
    assert hasattr(kj, "scrape") or hasattr(kj, "fetch_jobs")

    tc = TechcareerScraper()
    assert hasattr(tc, "scrape") or hasattr(tc, "fetch_jobs")

    uw = UpworkScraper()
    assert hasattr(uw, "scrape") or hasattr(uw, "fetch_jobs")

    rm = GlobalRemoteScraper()
    assert hasattr(rm, "scrape") or hasattr(rm, "fetch_jobs")
