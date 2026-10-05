import sqlite3

from backend.app.modules.outcome import analytics_engine


def test_conversion_funnel_excludes_raw_scraped_jobs(monkeypatch):
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
            (f"feed-{index}", "Draft", None, 0, None, None, "remoteok", 70, 0)
            for index in range(229)
        ]
        + [
            ("prepared", "Draft", None, 0, "A real tailored draft", None, "remoteok", 80, 0),
            ("unconfirmed-interview", "Interview", None, 0, None, None, "arbeitnow", 60, 0),
            ("confirmed-interview", "Interview", None, 1, None, None, "remoteok", 90, 0),
        ],
    )
    monkeypatch.setattr(analytics_engine, "get_db_connection", lambda: connection)

    result = analytics_engine.calculate_funnel_metrics()

    assert result["total_jobs"] == 2
    assert [(stage["stage"], stage["count"]) for stage in result["funnel_stages"]] == [
        ("Draft", 1),
        ("Human Review", 0),
        ("Applied", 1),
        ("Interview", 1),
        ("Offer", 0),
        ("Rejected", 0),
    ]
    assert sum(item["total_scraped"] for item in result["platform_performance"]) == 232
    assert result["observed_insights"]["minimum_verified_applications"] == 3
    assert result["observed_insights"]["best_observed_source"] is None
    assert result["observed_insights"]["best_observed_role"] is None
    connection.close()


def test_observed_insights_require_verified_application_sample_and_real_response(monkeypatch):
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
    rows = [(f"confirmed-{i}", "Interview" if i == 0 else "Applied", None, 1, "", "", "arbeitnow", 75, 0) for i in range(3)]
    connection.executemany("INSERT INTO scraped_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    connection.executemany(
        "INSERT INTO application_attribution VALUES (?, ?, ?, ?)",
        [(f"confirmed-{i}", 1, "Backend Engineer", "arbeitnow") for i in range(3)],
    )
    monkeypatch.setattr(analytics_engine, "get_db_connection", lambda: connection)

    result = analytics_engine.calculate_funnel_metrics()

    assert result["observed_insights"]["best_observed_source"]["platform"] == "Arbeitnow"
    assert result["observed_insights"]["best_observed_source"]["verified_application_sample"] == 3
    assert result["observed_insights"]["best_observed_role"]["target_role"] == "Backend Engineer"
    connection.close()
