import sqlite3

from backend.app.modules.outcome import analytics_engine
from backend.app.modules.scrape.scan_status import diagnose_empty_feed

READY = {"remote": {"configured": True}}


def _run(**overrides):
    return {"errors": [], "raw_fetched_count": 0, "total_scraped": 0, "duplicate_count": 0, "filtered": {}, **overrides}


def test_feed_with_jobs_needs_no_diagnosis():
    assert diagnose_empty_feed(_run(), READY, 3) is None


def test_missing_scan_is_separated_from_missing_source_setup():
    assert diagnose_empty_feed(None, READY, 0)["cause"] == "no_scan"
    assert diagnose_empty_feed(None, {"linkedin": {"configured": False}}, 0)["cause"] == "source_setup"


def test_filters_are_blamed_only_when_listings_were_fetched_and_all_removed():
    result = diagnose_empty_feed(
        _run(raw_fetched_count=40, filtered={"location_mismatch": 31, "work_mode_mismatch": 9}), READY, 0
    )
    assert result["cause"] == "filters"
    assert result["dominant_filter"] == "location_mismatch"
    assert result["counts"]["location_mismatch"] == 31


def test_quota_credentials_and_connection_errors_are_distinguished():
    quota = diagnose_empty_feed(_run(errors=["Apify daily run limit reached (20)."]), READY, 0)
    credentials = diagnose_empty_feed(_run(errors=["Apify API token is not configured."]), READY, 0)
    connection = diagnose_empty_feed(_run(errors=["Could not reach the Apify API. Check the network and try again."]), READY, 0)
    unknown = diagnose_empty_feed(_run(errors=["Actor returned a non-list dataset"]), READY, 0)
    assert [quota["cause"], credentials["cause"], connection["cause"], unknown["cause"]] == [
        "quota", "credentials", "connection", "source_error",
    ]
    assert quota["error"] == "Apify daily run limit reached (20)."


def test_source_quota_flag_marks_quota_even_with_a_generic_error():
    health = {"linkedin": {"configured": True, "quota_reached": True}}
    assert diagnose_empty_feed(_run(errors=["Linkedin: blocked"]), health, 0)["cause"] == "quota"


def test_clean_scan_without_listings_is_no_results_not_an_error():
    assert diagnose_empty_feed(_run(), READY, 0)["cause"] == "no_results"
    assert diagnose_empty_feed(_run(raw_fetched_count=5, total_scraped=5, duplicate_count=5), READY, 0)["cause"] == "all_processed"


def test_rejections_count_only_for_confirmed_applications(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE scraped_jobs (
            id TEXT, status TEXT, stale_at TEXT, submission_confirmed INTEGER,
            cover_letter TEXT, micro_portfolio TEXT, platform TEXT,
            match_score REAL, ghost_score REAL
        );
        CREATE TABLE application_attribution (
            job_id TEXT, profile_version INTEGER, target_role TEXT, platform TEXT
        );
        CREATE TABLE profile_revisions (version INTEGER, target_role TEXT, created_at TEXT);
        """
    )
    connection.executemany(
        "INSERT INTO scraped_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("applied", "Applied", None, 1, "", "", "remoteok", 70, 0),
            ("rejected", "Rejected", None, 1, "", "", "remoteok", 70, 0),
            ("interview", "Interview", None, 1, "", "", "remoteok", 70, 0),
            # Dismissed from the feed without applying: not an employer rejection.
            ("dismissed", "Rejected", None, 0, "", "", "remoteok", 70, 0),
        ],
    )
    connection.executemany(
        "INSERT INTO application_attribution VALUES (?, 1, 'Backend Engineer', 'remoteok')",
        [("applied",), ("rejected",), ("interview",)],
    )
    monkeypatch.setattr(analytics_engine, "get_db_connection", lambda: connection)

    result = analytics_engine.calculate_funnel_metrics()

    assert result["rejected_count"] == 1
    assert result["awaiting_response_count"] == 1
    source = result["platform_performance"][0]
    assert (source["applied"], source["interviews"], source["rejected"], source["awaiting_response"]) == (3, 1, 1, 1)
    role = result["role_performance"][0]
    assert (role["applications"], role["interviews"], role["rejected"], role["awaiting_response"]) == (3, 1, 1, 1)
    connection.close()
