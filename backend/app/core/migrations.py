"""Versioned, backend-portable schema upgrades for existing installations."""

from backend.app.core.database import is_postgres_database


def apply_migrations(connection, cursor=None):
    cursor = cursor or connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            revision TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.commit()
    cursor.execute("SELECT revision FROM schema_migrations")
    applied = {row["revision"] if isinstance(row, dict) else row[0] for row in cursor.fetchall()}

    migrations = {
        "0001_profile_application_inbox_fields": [
            ("candidate_profile", "work_preference", "TEXT DEFAULT ''"),
            ("candidate_profile", "languages_json", "TEXT DEFAULT '[]'"),
            ("candidate_profile", "github_url", "TEXT DEFAULT ''"),
            ("candidate_profile", "summary", "TEXT DEFAULT ''"),
            ("candidate_profile", "work_style", "TEXT DEFAULT ''"),
            ("candidate_profile", "writing_tone", "TEXT DEFAULT ''"),
            ("scraped_jobs", "application_execution_mode", "TEXT DEFAULT 'simulation'"),
            ("scraped_jobs", "submission_state", "TEXT DEFAULT 'not_started'"),
            ("scraped_jobs", "submission_confirmed", "INTEGER DEFAULT 0"),
            ("scraped_jobs", "submission_message", "TEXT DEFAULT ''"),
            ("inbox_messages", "source_provider", "TEXT DEFAULT ''"),
            ("inbox_messages", "external_message_id", "TEXT DEFAULT ''"),
        ],
        "0002_durable_background_jobs": [],
        "0003_job_source_health": [],
        "0004_search_application_insights": [
            ("scraped_jobs", "source_aliases_json", "TEXT DEFAULT '[]'"),
        ],
        "0005_candidate_career_preferences": [
            ("candidate_profile", "target_categories_json", "TEXT DEFAULT '[]'"),
            ("candidate_profile", "target_roles_json", "TEXT DEFAULT '[]'"),
        ],
        "0006_encrypted_llm_provider_credentials": [],
        "0007_scan_history_and_job_freshness": [],
        "0008_job_freshness_and_scan_metrics": [
            ("scraped_jobs", "first_seen_at", "TIMESTAMP"),
            ("scraped_jobs", "last_seen_at", "TIMESTAMP"),
            ("scraped_jobs", "stale_at", "TIMESTAMP"),
            ("job_scan_runs", "raw_fetched_count", "INTEGER NOT NULL DEFAULT 0"),
            ("job_scan_runs", "filtered_count", "INTEGER NOT NULL DEFAULT 0"),
            ("job_scan_runs", "duplicate_count", "INTEGER NOT NULL DEFAULT 0"),
        ],
        "0009_workflow_flags_and_history": [],
        "0010_cv_analysis_history": [],
        "0011_job_link_checks": [],
        "0012_profile_revision_snapshots": [
            ("profile_revisions", "profile_json", "TEXT NOT NULL DEFAULT '{}'"),
        ],
        "0013_apify_usage_history": [],
        "0014_follow_up_email_notifications": [
            ("candidate_profile", "follow_up_email_reminders", "INTEGER NOT NULL DEFAULT 0"),
            ("follow_up_queue", "email_notified_at", "TIMESTAMP"),
            ("follow_up_queue", "email_claimed_at", "TIMESTAMP"),
        ],
        "0015_encrypted_tailored_resume_packages": [
            ("application_packages", "tailored_profile_json", "TEXT NOT NULL DEFAULT ''"),
        ],
        "0016_encrypted_smtp_credentials": [],
        "0017_scan_filter_breakdown": [
            ("job_scan_runs", "filtered_json", "TEXT NOT NULL DEFAULT '{}'"),
        ],
        "0018_draft_source_deadlines_company_boards": [
            # Which engine wrote the saved cover letter; lets the UI flag template text.
            ("scraped_jobs", "draft_source", "TEXT NOT NULL DEFAULT ''"),
            # Application deadline as an ISO date (YYYY-MM-DD) when the source publishes one.
            ("scraped_jobs", "deadline", "TEXT NOT NULL DEFAULT ''"),
        ],
        "0019_ai_job_reviews": [
            # Cached language-model judgement of the job against one profile version.
            ("scraped_jobs", "ai_review_json", "TEXT NOT NULL DEFAULT ''"),
        ],
        "0020_saved_search_llm_provider": [
            # AI that reviews this search's results when it runs on schedule; empty = no AI review.
            ("saved_searches", "llm_provider", "TEXT NOT NULL DEFAULT ''"),
        ],
        "0021_scraped_jobs_indexes": [],
        "0022_saved_search_remote_type": [
            ("saved_searches", "remote_type", "TEXT NOT NULL DEFAULT ''"),
        ],
        "0023_saved_cv_document": [],
        "0024_page_visits": [],
    }
    for revision, columns in migrations.items():
        if revision in applied:
            continue
        for table, column, definition in columns:
            if is_postgres_database():
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}")
            else:
                cursor.execute(f"PRAGMA table_info({table})")
                present = {row[1] for row in cursor.fetchall()}
                if column not in present:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        if revision == "0002_durable_background_jobs":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS background_jobs (
                    id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    result_json TEXT,
                    error_text TEXT,
                    idempotency_key TEXT UNIQUE,
                    celery_task_id TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 4,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_background_jobs_created ON background_jobs(created_at)")
        if revision == "0003_job_source_health":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_source_settings (
                    source TEXT PRIMARY KEY,
                    actor_id TEXT NOT NULL DEFAULT '',
                    encrypted_token TEXT NOT NULL DEFAULT '',
                    input_json TEXT NOT NULL DEFAULT '{}',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_source_runs (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    jobs_count INTEGER NOT NULL DEFAULT 0,
                    error_text TEXT,
                    latency_ms REAL NOT NULL DEFAULT 0,
                    started_at REAL NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_source_runs_source_time ON job_source_runs(source, started_at)")
        if revision == "0004_search_application_insights":
            cursor.execute("CREATE TABLE IF NOT EXISTS saved_searches (id TEXT PRIMARY KEY, name TEXT NOT NULL, queries_json TEXT NOT NULL, location TEXT NOT NULL DEFAULT '', min_match_score REAL NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            cursor.execute("CREATE TABLE IF NOT EXISTS user_notifications (id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, href TEXT NOT NULL DEFAULT '/jobs', read_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            cursor.execute("CREATE TABLE IF NOT EXISTS profile_revisions (version INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL, target_role TEXT NOT NULL DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            cursor.execute("CREATE TABLE IF NOT EXISTS application_attribution (job_id TEXT PRIMARY KEY, profile_version INTEGER NOT NULL, target_role TEXT NOT NULL DEFAULT '', platform TEXT NOT NULL DEFAULT '', updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            cursor.execute("CREATE TABLE IF NOT EXISTS application_packages (id TEXT PRIMARY KEY, job_id TEXT NOT NULL, profile_version INTEGER NOT NULL, cover_letter TEXT NOT NULL, tailoring_json TEXT NOT NULL DEFAULT '{}', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_notifications_created ON user_notifications(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_application_attribution_profile ON application_attribution(profile_version)")
        if revision == "0006_encrypted_llm_provider_credentials":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS llm_provider_credentials (
                    provider TEXT PRIMARY KEY,
                    encrypted_api_key TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        if revision == "0007_scan_history_and_job_freshness":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_scan_runs (
                    id TEXT PRIMARY KEY,
                    query_json TEXT NOT NULL DEFAULT '[]',
                    platforms_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'running',
                    total_scraped INTEGER NOT NULL DEFAULT 0,
                    newly_saved_count INTEGER NOT NULL DEFAULT 0,
                    removed_count INTEGER NOT NULL DEFAULT 0,
                    errors_json TEXT NOT NULL DEFAULT '[]',
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
        if revision == "0008_job_freshness_and_scan_metrics":
            cursor.execute("UPDATE scraped_jobs SET first_seen_at = COALESCE(first_seen_at, created_at), last_seen_at = COALESCE(last_seen_at, created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_scan_runs_started ON job_scan_runs(started_at DESC)")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_source_snapshots (
                    platform TEXT PRIMARY KEY,
                    last_scan_id TEXT NOT NULL DEFAULT '',
                    last_success_at TIMESTAMP,
                    current_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        if revision == "0009_workflow_flags_and_history":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_flags (
                    job_id TEXT PRIMARY KEY,
                    favorite INTEGER NOT NULL DEFAULT 0,
                    hidden INTEGER NOT NULL DEFAULT 0,
                    note TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_flags_favorite ON job_flags(favorite)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_flags_hidden ON job_flags(hidden)")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS application_status_history (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    from_status TEXT NOT NULL DEFAULT '',
                    to_status TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'kanban',
                    note TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_application_status_history_job ON application_status_history(job_id, created_at DESC)")
        if revision == "0010_cv_analysis_history":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cv_analysis_runs (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL DEFAULT '',
                    content_hash TEXT NOT NULL,
                    page_count INTEGER,
                    character_count INTEGER NOT NULL DEFAULT 0,
                    ai_requested INTEGER NOT NULL DEFAULT 0,
                    ai_used INTEGER NOT NULL DEFAULT 0,
                    ai_provider TEXT,
                    quality_json TEXT NOT NULL DEFAULT '{}',
                    analysis_json TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cv_analysis_runs_created ON cv_analysis_runs(created_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cv_analysis_runs_hash ON cv_analysis_runs(content_hash)")
        if revision == "0011_job_link_checks":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_link_checks (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'unknown',
                    status_code INTEGER,
                    checked_url TEXT NOT NULL DEFAULT '',
                    final_url TEXT NOT NULL DEFAULT '',
                    error_text TEXT NOT NULL DEFAULT '',
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_link_checks_status ON job_link_checks(status)")
        if revision == "0013_apify_usage_history":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS apify_usage_history (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    configured_keys INTEGER NOT NULL DEFAULT 0,
                    valid_keys INTEGER NOT NULL DEFAULT 0,
                    budget_usd REAL NOT NULL DEFAULT 0,
                    used_usd REAL NOT NULL DEFAULT 0,
                    remaining_usd REAL NOT NULL DEFAULT 0,
                    percent_used REAL NOT NULL DEFAULT 0,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_apify_usage_history_checked ON apify_usage_history(checked_at DESC)")
        if revision == "0016_encrypted_smtp_credentials":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS smtp_credentials (
                    id TEXT PRIMARY KEY,
                    encrypted_config TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        cursor.execute("DROP INDEX IF EXISTS idx_inbox_external_message")
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_inbox_external_message "
            "ON inbox_messages(source_provider, external_message_id) "
            "WHERE external_message_id <> ''"
        )
        if revision == "0018_draft_source_deadlines_company_boards":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS company_boards (
                    provider TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (provider, slug)
                )
            """)
        if revision == "0021_scraped_jobs_indexes":
            # The feed, the board and ranking all filter and sort this table; without these every query scans it.
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_jobs_feed ON scraped_jobs(stale_at, match_score DESC, created_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_jobs_platform ON scraped_jobs(platform)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_jobs_status ON scraped_jobs(status)")
        if revision == "0024_page_visits":
            # Which screens are actually opened; kept on this machine to decide what to remove.
            cursor.execute("CREATE TABLE IF NOT EXISTS page_visits (path TEXT NOT NULL, day TEXT NOT NULL, visits INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (path, day))")
        if revision == "0023_saved_cv_document":
            # The candidate's own CV file, encrypted; one row per workspace.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cv_documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    content_type TEXT NOT NULL DEFAULT '',
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    content_hash TEXT NOT NULL,
                    page_count INTEGER,
                    encrypted_content TEXT NOT NULL,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        cursor.execute("INSERT INTO schema_migrations(revision) VALUES (?)", (revision,))
        connection.commit()
