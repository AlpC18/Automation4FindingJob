"""robots.txt is honoured, and scraped text cannot run as script in a generated report."""

from pathlib import Path

from backend.app.modules.outcome import html_report as report_module
from backend.app.tools import robots_check

ROBOTS = """
User-agent: *
Disallow: /private
Allow: /private/jobs
Disallow: /*.pdf$

User-agent: CareerAgent-Bot
Disallow: /bots-not-welcome
"""


def test_the_most_specific_rule_wins():
    assert robots_check.allowed(ROBOTS, "*", "/jobs/1") is True
    assert robots_check.allowed(ROBOTS, "*", "/private/notes") is False
    assert robots_check.allowed(ROBOTS, "*", "/private/jobs/1") is True
    assert robots_check.allowed(ROBOTS, "*", "/files/cv.pdf") is False


def test_agents_listed_together_share_the_rules_that_follow():
    shared = "User-agent: *\nUser-agent: OtherBot\nDisallow: /\n"

    assert robots_check.allowed(shared, "*", "/jobs") is False
    assert robots_check.allowed(shared, "OtherBot", "/jobs") is False


def _published(monkeypatch, body, code=200):
    monkeypatch.setattr(robots_check, "_fetch", lambda url, ua: (body, code))


def test_a_path_blocked_for_our_bot_is_refused(monkeypatch):
    _published(monkeypatch, ROBOTS)

    assert robots_check.check_robots_permission("https://site.test/bots-not-welcome/x")[0] is False
    assert robots_check.check_robots_permission("https://site.test/private/notes")[0] is False
    assert robots_check.check_robots_permission("https://site.test/jobs/1")[0] is True


def test_no_robots_file_allows_and_an_unreadable_one_refuses(monkeypatch):
    _published(monkeypatch, "", code=404)
    assert robots_check.check_robots_permission("https://site.test/jobs")[0] is True

    _published(monkeypatch, "<html>Access denied</html>", code=403)
    assert robots_check.check_robots_permission("https://site.test/jobs")[0] is False

    def offline(url, ua):
        raise ConnectionError("offline")

    monkeypatch.setattr(robots_check, "_fetch", offline)
    assert robots_check.check_robots_permission("https://site.test/jobs")[0] is False


def test_reports_escape_scraped_text_and_drop_script_links(monkeypatch, tmp_path):
    monkeypatch.setattr(report_module, "_reports_dir", lambda: tmp_path)
    hostile = {
        "title": "<script>alert(1)</script>", "company": "<img src=x onerror=alert(2)>",
        "url": "javascript:alert(3)", "match_score": 80, "status": "new",
    }

    jobs_report = report_module.html_report_generator.generate_job_search_report([hostile], {})
    pipeline_report = report_module.html_report_generator.generate_pipeline_report([{**hostile, "notes": "<b>x</b>"}])

    for report in (jobs_report, pipeline_report):
        html = Path(report["report_path"]).read_text(encoding="utf-8")
        assert "<script>alert" not in html and "<img src=x" not in html and "<b>x</b>" not in html
        assert "javascript:" not in html
        assert "&lt;script&gt;" in html
