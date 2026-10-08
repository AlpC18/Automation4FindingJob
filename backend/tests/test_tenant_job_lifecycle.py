"""Regression coverage for tenant isolation and durable work records."""

import asyncio
import json
import sqlite3

import pytest

from backend.app.core.config import settings
from backend.app.core.database import get_db_connection, init_auth_db, init_db, init_tenant_db, use_tenant
from backend.app.core.tenant import tenant_data_path
from backend.app.modules.apply.auto_apply_pipeline import AutoApplyPipeline
from backend.app.modules.scrape.unified_scraper import UnifiedScraper
from backend.app.tasks.job_store import create_job, get_job, list_jobs, update_job


@pytest.fixture
def isolated_database(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATA_PATH", tmp_path)
    monkeypatch.setattr(settings, "BACKUP_DIR", None)
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'control.db'}")
    monkeypatch.setattr(settings, "MULTI_TENANT_ENABLED", True)
    init_db()
    init_auth_db()
    return tmp_path


def test_job_lifecycle_is_idempotent_and_tenant_isolated(isolated_database):
    init_tenant_db("tenant-alpha")
    init_tenant_db("tenant-beta")

    with use_tenant("tenant-alpha"):
        job, created = create_job("scrape", {"keywords": "backend"}, "same-request")
        duplicate, duplicate_created = create_job("scrape", {"keywords": "backend"}, "same-request")
        assert created is True
        assert duplicate_created is False
        assert duplicate["id"] == job["id"]

        update_job(job["id"], "running", increment_attempt=True)
        update_job(job["id"], "succeeded", result={"saved": 2})
        stored = get_job(job["id"])
        assert stored["status"] == "succeeded"
        assert stored["attempts"] == 1
        assert stored["result_json"] == '{"saved": 2}'

    with use_tenant("tenant-beta"):
        assert get_job(job["id"]) is None
        assert list_jobs() == []


def test_application_submission_persists_outcome_and_private_files(isolated_database, monkeypatch):
    init_tenant_db("candidate-one")
    pipeline = AutoApplyPipeline()
    with use_tenant("candidate-one"):
        pipeline._queue["applications"]["job-key"] = {
            "status": "approved",
            "url": "https://example.test/jobs/1",
            "title": "Engineer",
            "company": "Example",
        }
        pipeline._save()
        result = asyncio.run(pipeline.submit_approved_application("job-key"))
        persisted = get_job(result["job_id"])

        assert result["success"] is True
        assert result["submission_confirmed"] is False
        assert persisted["job_type"] == "application_handoff"
        assert persisted["status"] == "succeeded"
        assert persisted["result_json"] == '{"submission_confirmed": false, "job_key": "job-key", "handoff_required": true}'
        assert result["application"]["status"] == "awaiting_user_submission"
        assert tenant_data_path("auto_apply_queue.json").parent.name == "candidateone"


def test_manual_submission_confirmation_is_required_before_application_is_counted(isolated_database):
    from backend.app.core.database import get_db_connection

    init_tenant_db("manual-confirm")
    with use_tenant("manual-confirm"):
        connection = get_db_connection()
        try:
            connection.cursor().execute(
                "INSERT INTO scraped_jobs(id, title, company, platform, url, description) VALUES (?, ?, ?, ?, ?, ?)",
                ("job-key", "Engineer", "Example", "linkedin", "https://example.test/job", "A real job description."),
            )
            connection.commit()
        finally:
            connection.close()

        pipeline = AutoApplyPipeline()
        pipeline._queue["applications"]["job-key"] = {
            "status": "awaiting_user_submission", "url": "https://example.test/job",
            "title": "Engineer", "company": "Example",
        }
        result = pipeline.confirm_manual_submission("job-key")
        assert result["success"] is True
        assert pipeline.get_today_count() == 1

        connection = get_db_connection()
        try:
            row = connection.cursor().execute(
                "SELECT status, submission_confirmed FROM scraped_jobs WHERE id = 'job-key'"
            ).fetchone()
            assert row["status"] == "Applied"
            assert row["submission_confirmed"] == 1
        finally:
            connection.close()


def test_versioned_migrations_create_durable_job_table(isolated_database):
    from backend.app.core.database import get_db_connection

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT revision FROM schema_migrations ORDER BY revision")
        assert [row[0] for row in cursor.fetchall()] == [
            "0001_profile_application_inbox_fields",
            "0002_durable_background_jobs",
            "0003_job_source_health",
            "0004_search_application_insights",
                "0005_candidate_career_preferences",
            "0006_encrypted_llm_provider_credentials",
            "0007_scan_history_and_job_freshness",
            "0008_job_freshness_and_scan_metrics",
            "0009_workflow_flags_and_history",
            "0010_cv_analysis_history",
            "0011_job_link_checks",
            "0012_profile_revision_snapshots",
            "0013_apify_usage_history",
            "0014_follow_up_email_notifications",
            "0015_encrypted_tailored_resume_packages",
            "0016_encrypted_smtp_credentials",
            "0017_scan_filter_breakdown",
        "0018_draft_source_deadlines_company_boards",
        "0019_ai_job_reviews",
        "0020_saved_search_llm_provider",
        "0021_scraped_jobs_indexes",
        "0022_saved_search_remote_type",
        "0023_saved_cv_document",
        "0024_page_visits",
            ]
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'background_jobs'")
        assert cursor.fetchone() is not None
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'job_flags'")
        assert cursor.fetchone() is not None
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'application_status_history'")
        assert cursor.fetchone() is not None
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'cv_analysis_runs'")
        assert cursor.fetchone() is not None
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'job_link_checks'")
        assert cursor.fetchone() is not None
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'apify_usage_history'")
        assert cursor.fetchone() is not None
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'llm_provider_credentials'")
        assert cursor.fetchone() is not None
        cursor.execute("PRAGMA table_info(scraped_jobs)")
        assert {row[1] for row in cursor.fetchall()} >= {"first_seen_at", "last_seen_at", "stale_at"}
    finally:
        connection.close()


def test_cv_analysis_history_keeps_metadata_without_resume_contents(isolated_database):
    from backend.app.modules.setup.cv_analysis_history import list_analysis_runs, record_analysis_run

    init_tenant_db("cv-history")
    with use_tenant("cv-history"):
        run = record_analysis_run(
            filename="resume.pdf",
            content_hash="hash-123",
            page_count=2,
            character_count=2400,
            ai_requested=False,
            ai_used=False,
            ai_provider=None,
            quality={"score": 72, "grade": "good"},
            analysis={"gaps": ["Add measurable outcomes"]},
        )
        conn = get_db_connection()
        try:
            stored_filename = conn.cursor().execute(
                "SELECT filename FROM cv_analysis_runs WHERE id = ?", (run["id"],)
            ).fetchone()["filename"]
        finally:
            conn.close()
        history = list_analysis_runs()

    assert history[0]["id"] == run["id"]
    assert stored_filename.startswith("fernet$")
    assert history[0]["filename"] == "resume.pdf"
    assert history[0]["quality"]["score"] == 72
    assert history[0]["analysis"] == {}
    assert "resume_text" not in history[0]
    assert "optimized_cv_text" not in history[0]


def test_due_follow_up_notifications_are_durable_deduplicated_and_resolvable(isolated_database):
    from backend.app.api.routers.orchestration import resolve_follow_up_reminders
    from backend.app.modules.outcome.follow_up_cadence import follow_up_cadence_engine
    from backend.app.modules.outcome.follow_up_scheduler import schedule_follow_ups_for_job

    tenant_id = "durable-follow-up"
    init_tenant_db(tenant_id)
    with use_tenant(tenant_id):
        conn = get_db_connection()
        try:
            conn.cursor().execute(
                """INSERT INTO scraped_jobs
                   (id, title, company, platform, description, status, applied_at, submission_confirmed)
                   VALUES (?, ?, ?, ?, ?, 'Applied', ?, 1)""",
                ("follow-up-job", "Backend Engineer", "Example Co", "test", "Test job", "2000-01-01T00:00:00+00:00"),
            )
            conn.commit()
        finally:
            conn.close()

        job = {"id": "follow-up-job", "company": "Example Co", "title": "Backend Engineer"}
        schedule_follow_ups_for_job(job)
        schedule_follow_ups_for_job(job)
        conn = get_db_connection()
        try:
            conn.cursor().execute("UPDATE follow_up_queue SET scheduled_date = '2000-01-02' WHERE job_id = ?", (job["id"],))
            conn.commit()
            count = conn.cursor().execute("SELECT COUNT(*) AS count FROM follow_up_queue WHERE job_id = ?", (job["id"],)).fetchone()["count"]
        finally:
            conn.close()

        pending = follow_up_cadence_engine.get_pending_follow_ups()
        assert count == 3
        assert len(pending) == 1
        assert pending[0]["due_days"] == [4, 9, 14]

        conn = get_db_connection()
        try:
            notification_count = conn.cursor().execute(
                "SELECT COUNT(*) AS count FROM user_notifications WHERE id LIKE 'follow-up-%'"
            ).fetchone()["count"]
        finally:
            conn.close()
        assert notification_count == 3

        result = resolve_follow_up_reminders(job["id"])
        assert result["resolved_count"] == 3
        assert follow_up_cadence_engine.get_pending_follow_ups() == []


def test_celery_scrape_dispatch_keeps_all_search_filters(isolated_database, monkeypatch):
    from types import SimpleNamespace
    from backend.app.tasks import worker_tasks
    from backend.app.tasks.dispatcher import task_dispatcher

    tenant_id = "queued-full-search"
    init_tenant_db(tenant_id)
    calls = []

    class FakeScrapeTask:
        @staticmethod
        def delay(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(id="celery-task-123")

    monkeypatch.setattr(task_dispatcher, "is_celery_active", lambda: True)
    monkeypatch.setattr(worker_tasks, "task_scrape_jobs", FakeScrapeTask)
    options = {
        "platforms": ["remote", "linkedin"],
        "queries": ["Backend Engineer", "Python Developer"],
        "location_preference": "Berlin",
        "remote_type": "hybrid",
        "replace_current_feed": False,
    }

    with use_tenant(tenant_id):
        result = asyncio.run(task_dispatcher.dispatch_scrape(
            keywords="Backend Engineer",
            location="Berlin",
            tenant_id=tenant_id,
            idempotency_key="full-scan-once",
            scrape_options=options,
        ))
        persisted = get_job(result["job_id"])

    assert result["dispatch_mode"] == "CELERY_REDIS"
    assert result["status"] == "QUEUED"
    assert calls[0]["target_platforms"] == options["platforms"]
    assert calls[0]["queries"] == options["queries"]
    assert calls[0]["location_preference"] == "Berlin"
    assert calls[0]["remote_type"] == "hybrid"
    assert calls[0]["replace_current_feed"] is False
    assert json.loads(persisted["payload_json"])["scrape_options"]["queries"] == options["queries"]


def test_follow_up_email_is_opt_in_and_sent_once_only_to_candidate(isolated_database, monkeypatch):
    from fastapi import HTTPException
    from backend.app.api.profile import encrypt_profile_values
    from backend.app.api.routers import setup
    from backend.app.modules.outcome import follow_up_cadence
    from backend.app.modules.outcome.follow_up_scheduler import schedule_follow_ups_for_job

    tenant_id = "follow-up-email-opt-in"
    init_tenant_db(tenant_id)
    sent = []
    monkeypatch.setattr(setup, "smtp_is_configured", lambda: False)
    with use_tenant(tenant_id):
        conn = get_db_connection()
        try:
            conn.cursor().execute(
                "INSERT INTO candidate_profile (email) VALUES (?)",
                encrypt_profile_values(("candidate@example.test",)),
            )
            conn.cursor().execute(
                """INSERT INTO scraped_jobs
                   (id, title, company, platform, description, status, applied_at, submission_confirmed)
                   VALUES (?, ?, ?, ?, ?, 'Applied', ?, 1)""",
                ("email-follow-up-job", "Backend Engineer", "Example Co", "test", "Job details", "2000-01-01T00:00:00+00:00"),
            )
            conn.commit()
        finally:
            conn.close()

        assert setup.get_notification_preferences()["follow_up_email_reminders"] is False
        with pytest.raises(HTTPException) as error:
            setup.update_notification_preferences(setup.FollowUpEmailPreferenceRequest(enabled=True))
        assert error.value.status_code == 503

        monkeypatch.setattr(setup, "smtp_is_configured", lambda: True)
        preference = setup.update_notification_preferences(setup.FollowUpEmailPreferenceRequest(enabled=True))
        assert preference["follow_up_email_reminders"] is True
        monkeypatch.setattr(follow_up_cadence, "smtp_is_configured", lambda: True)
        monkeypatch.setattr(follow_up_cadence, "send_security_email", lambda *args: sent.append(args))

        job = {"id": "email-follow-up-job", "company": "Example Co", "title": "Backend Engineer"}
        schedule_follow_ups_for_job(job)
        conn = get_db_connection()
        try:
            conn.cursor().execute("UPDATE follow_up_queue SET scheduled_date = '2000-01-02' WHERE job_id = ?", (job["id"],))
            conn.commit()
        finally:
            conn.close()

        follow_up_cadence.FollowUpCadenceEngine.emit_due_follow_up_notifications()
        follow_up_cadence.FollowUpCadenceEngine.emit_due_follow_up_notifications()

    assert len(sent) == 3
    assert all(message[0] == "candidate@example.test" for message in sent)
    assert all("işverene e-posta gönderilmedi" in message[2] for message in sent)
    assert {message[1] for message in sent} == {
        "Başvuru takip hatırlatması — Example Co",
    }


def test_job_link_check_blocks_private_network_targets(isolated_database):
    from backend.app.modules.scrape.job_link_health import check_job_link
    from backend.app.core.database import get_db_connection

    init_tenant_db("link-check")
    with use_tenant("link-check"):
        conn = get_db_connection()
        try:
            conn.cursor().execute(
                "INSERT INTO scraped_jobs(id, title, company, platform, url, description) VALUES (?, ?, ?, ?, ?, ?)",
                ("private-link", "Engineer", "Example", "remoteok", "http://127.0.0.1:8000/private", "desc"),
            )
            conn.commit()
        finally:
            conn.close()
        result = check_job_link("private-link")
        check_conn = get_db_connection()
        try:
            stored = check_conn.cursor().execute("SELECT status, error_text FROM job_link_checks WHERE job_id = ?", ("private-link",)).fetchone()
        finally:
            check_conn.close()
        assert result["status"] == "invalid"
        assert stored["status"] == "invalid"
        assert "yerel" in stored["error_text"].lower() or "özel" in stored["error_text"].lower()


def test_scrape_filters_without_fabricating_preferences_and_archives_stale_feed(isolated_database):
    init_tenant_db("scrape-candidate")
    scraper = UnifiedScraper()

    class FakeSource:
        current = [
            {"id": "berlin-remote", "title": "Backend Engineer", "company": "Example", "platform": "remoteok", "url": "https://jobs.example/1", "location": "Berlin", "remote_type": "Remote", "description": "Backend role with a real description."},
            {"id": "unknown-location", "title": "Backend Engineer", "company": "Unknown Co", "platform": "remoteok", "url": "https://jobs.example/2", "location": "Unspecified", "remote_type": "Remote", "description": "Backend role with a real description."},
            {"id": "unknown-mode", "title": "Backend Engineer", "company": "Unknown Mode Co", "platform": "remoteok", "url": "https://jobs.example/3", "location": "Berlin", "remote_type": "Unknown", "description": "Backend role with a real description."},
        ]

        def fetch_jobs(self, query, location=None):
            return list(self.current)

    source = FakeSource()
    scraper.scrapers = {"remote": source}
    with use_tenant("scrape-candidate"):
        first = scraper.run_multi_platform_scrape(
            queries=["Backend Engineer"], target_platforms=["remote"],
            location_preference="Berlin", remote_type="remote",
        )
        assert first["raw_fetched_count"] == 3
        assert first["total_scraped"] == 1
        assert first["filtered"]["location_mismatch"] == 1
        assert first["filtered"]["work_mode_mismatch"] == 1
        assert first["jobs"][0]["location"] == "Berlin"

        source.current = []
        second = scraper.run_multi_platform_scrape(queries=["Backend Engineer"], target_platforms=["remote"])
        assert second["archived_count"] == 1
        assert second["current_total"] == 0

        from backend.app.core.database import get_db_connection
        connection = get_db_connection()
        try:
            row = connection.cursor().execute(
                "SELECT first_seen_at, last_seen_at, stale_at FROM scraped_jobs WHERE id = ?", ("berlin-remote",)
            ).fetchone()
            assert row["first_seen_at"] and row["last_seen_at"] and row["stale_at"]
        finally:
            connection.close()


def test_apify_scrape_applies_per_run_item_and_charge_caps(isolated_database, monkeypatch):
    from backend.app.modules.scrape import live_sources

    init_db()
    captured = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return [{"id": "one", "title": "Engineer", "company": "Example", "url": "https://example.test/1", "location": "Berlin"}]

    monkeypatch.setattr(live_sources, "get_source_config", lambda _source: {
        "enabled": True, "actor_id": "account/actor", "api_token": "test-token", "api_tokens": ["test-token"], "input_json": "{}", "has_custom_config": True,
    })
    monkeypatch.setattr(live_sources, "select_apify_account", lambda _source, _cap: ("test-token", 0.2))
    monkeypatch.setattr(live_sources.httpx, "post", lambda url, **kwargs: (captured.update({"url": url, **kwargs}) or FakeResponse()))
    monkeypatch.setattr(settings, "APIFY_MAX_ITEMS_PER_RUN", 7)
    monkeypatch.setattr(settings, "APIFY_MAX_ACTOR_RUNS_PER_DAY", 0)
    monkeypatch.setattr(settings, "APIFY_MAX_TOTAL_CHARGE_USD", 0.35)

    result = live_sources.apify_job_source.fetch("linkedin", "Engineer", "Berlin")
    assert len(result) == 1
    assert captured["params"]["maxItems"] == 7
    assert captured["params"]["maxTotalChargeUsd"] == 0.2
    assert captured["json"]["location"] == "Berlin"


def test_stale_worker_jobs_become_retryable_failures(isolated_database):
    from backend.app.core.database import get_db_connection

    job, _ = create_job("scrape", {"keywords": "designer"})
    update_job(job["id"], "running", increment_attempt=True)
    connection = get_db_connection()
    try:
        connection.cursor().execute(
            "UPDATE background_jobs SET updated_at = '2000-01-01 00:00:00' WHERE id = ?", (job["id"],)
        )
        connection.commit()
    finally:
        connection.close()

    recovered = list_jobs()
    assert recovered[0]["status"] == "failed"
    assert "heartbeat expired" in recovered[0]["error_text"]


def test_provider_tokens_are_encrypted_and_never_public(isolated_database, monkeypatch):
    from cryptography.fernet import Fernet
    from backend.app.core.database import get_db_connection
    from backend.app.modules.scrape.source_registry import public_source_config, save_source_config

    monkeypatch.setattr(settings, "APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    save_source_config("linkedin", actor_id="team/linkedin", api_token="secret-token", input_json='{"limit": 5}', enabled=True)
    assert public_source_config("linkedin")["token_configured"] is True
    assert "secret-token" not in str(public_source_config("linkedin"))
    connection = get_db_connection()
    try:
        row = connection.cursor()
        row.execute("SELECT encrypted_token FROM job_source_settings WHERE source = 'linkedin'")
        assert row.fetchone()[0].startswith("fernet$")
    finally:
        connection.close()


def test_multiple_apify_tokens_are_encrypted_as_one_source_secret(isolated_database, monkeypatch):
    from cryptography.fernet import Fernet
    from backend.app.modules.scrape.source_registry import get_source_config, public_source_config, save_source_config

    monkeypatch.setattr(settings, "APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    save_source_config("linkedin", actor_id="valig/linkedin-jobs-scraper", api_token="first-secret\nsecond-secret", input_json="{}", enabled=True)
    config = get_source_config("linkedin")
    assert config["api_tokens"] == ["first-secret", "second-secret"]
    assert public_source_config("linkedin")["token_count"] == 2
    assert "first-secret" not in str(public_source_config("linkedin"))
    assert "second-secret" not in str(public_source_config("linkedin"))


def test_unreadable_saved_apify_token_requires_reentry_without_breaking_health(isolated_database, monkeypatch):
    from cryptography.fernet import Fernet, InvalidToken

    from backend.app.modules.scrape import source_registry

    monkeypatch.setattr(settings, "APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    source_registry.save_source_config(
        "linkedin",
        actor_id="test/actor",
        api_token="saved-token",
        input_json="{}",
        enabled=True,
    )

    def unreadable_secret(_value):
        raise InvalidToken

    monkeypatch.setattr(source_registry, "decrypt_secret", unreadable_secret)
    config = source_registry.get_source_config("linkedin")
    assert config["api_tokens"] == []
    assert config["token_needs_reentry"] is True
    assert source_registry.public_source_config("linkedin")["token_needs_reentry"] is True


def test_sqlite_backup_endpoint_returns_a_consistent_database_snapshot(isolated_database):
    from backend.app.api.routers.system import download_database_backup

    database_path = isolated_database / "career_engine.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE backup_probe(value TEXT)")
        connection.execute("INSERT INTO backup_probe(value) VALUES ('snapshot-ok')")

    response = download_database_backup()

    async def read_response():
        return b"".join([chunk async for chunk in response.body_iterator])

    data = asyncio.run(read_response())
    assert data.startswith(b"SQLite format 3")
    snapshot_path = isolated_database / "downloaded-backup.sqlite3"
    snapshot_path.write_bytes(data)
    snapshot = sqlite3.connect(snapshot_path)
    assert snapshot.execute("SELECT value FROM backup_probe").fetchone()[0] == "snapshot-ok"
    assert response.headers["cache-control"] == "no-store"
    snapshot.close()


def test_encrypted_backup_restores_global_workspace_and_keeps_safety_copy(isolated_database, monkeypatch):
    from cryptography.fernet import Fernet
    from backend.app.core.backup_manager import BACKUP_MAGIC, create_sqlite_backup, restore_sqlite_workspace

    monkeypatch.setattr(settings, "APP_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    database_path = isolated_database / "career_engine.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE backup_probe(value TEXT)")
        connection.execute("INSERT INTO backup_probe(value) VALUES ('before-restore')")

    backup_path = create_sqlite_backup(force=True)
    encrypted_backup = backup_path.read_bytes()
    assert encrypted_backup.startswith(BACKUP_MAGIC)
    assert b"before-restore" not in encrypted_backup

    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE backup_probe SET value = 'after-backup'")

    safety_copy = restore_sqlite_workspace(encrypted_backup, None)
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT value FROM backup_probe").fetchone()[0] == "before-restore"
    assert (isolated_database / "backups" / safety_copy).is_file()


def test_backup_restore_targets_only_the_requested_tenant_workspace(isolated_database, monkeypatch):
    from cryptography.fernet import Fernet
    from backend.app.core.backup_manager import create_sqlite_backup, restore_sqlite_workspace

    monkeypatch.setattr(settings, "APP_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    init_tenant_db("restore-alpha")
    with use_tenant("restore-alpha"):
        connection = get_db_connection()
        try:
            connection.cursor().execute("CREATE TABLE tenant_backup_probe(value TEXT)")
            connection.cursor().execute("INSERT INTO tenant_backup_probe(value) VALUES (?)", ("alpha-original",))
            connection.commit()
        finally:
            connection.close()
    backup_path = create_sqlite_backup(force=True)
    with use_tenant("restore-alpha"):
        connection = get_db_connection()
        try:
            connection.cursor().execute("UPDATE tenant_backup_probe SET value = 'alpha-changed'")
            connection.commit()
        finally:
            connection.close()
        restore_sqlite_workspace(backup_path.read_bytes(), "restore-alpha")
        connection = get_db_connection()
        try:
            value = connection.cursor().execute("SELECT value FROM tenant_backup_probe").fetchone()[0]
        finally:
            connection.close()
        assert value == "alpha-original"
    with pytest.raises(ValueError, match="çalışma alanını içermiyor"):
        restore_sqlite_workspace(backup_path.read_bytes(), "restore-beta")


def test_inbox_reply_is_not_marked_replied_when_smtp_did_not_send(isolated_database, monkeypatch):
    from backend.app.modules.outcome.inbox_agent import inbox_agent
    from backend.app.modules.apply.email_finder import email_finder

    init_tenant_db("inbox-send-status")
    with use_tenant("inbox-send-status"):
        conn = get_db_connection()
        try:
            conn.cursor().execute(
                "INSERT INTO inbox_messages(sender_email, subject, body_text, classification, status) VALUES (?, ?, ?, ?, ?)",
                ("recruiter@example.test", "Interview", "Let's talk", "INTERVIEW_INVITE", "UNREAD"),
            )
            conn.commit()
            message_id = conn.cursor().execute("SELECT last_insert_rowid()").fetchone()[0]
        finally:
            conn.close()

        monkeypatch.setattr(email_finder, "send_smtp_outreach", lambda **_kwargs: {"status": "NOT_CONFIGURED"})
        result = inbox_agent.approve_and_send_reply(message_id, "Thank you")
        assert result["status"] == "FAILED"
        conn = get_db_connection()
        try:
            current_status = conn.cursor().execute("SELECT status FROM inbox_messages WHERE id = ?", (message_id,)).fetchone()[0]
        finally:
            conn.close()
        assert current_status == "UNREAD"


def test_job_quality_filters_expired_records_and_normalizes_duplicate_links():
    from backend.app.modules.scrape.job_quality import job_match_keys, quality_issue

    fresh = {"title": "Backend Engineer", "company": "Example", "url": "https://jobs.example/1", "description": "A detailed opportunity with useful responsibilities."}
    assert quality_issue(fresh) is None
    assert quality_issue({**fresh, "posted_date": "4 months ago"}) == "expired_over_90_days"
    assert job_match_keys(fresh)[0] == job_match_keys({**fresh, "url": "https://jobs.example/1/?utm_source=newsletter"})[0]
    assert job_match_keys(fresh)[-1] == job_match_keys({**fresh, "url": "https://other-board.test/opening/2"})[-1]


def test_profile_versions_change_only_when_candidate_data_changes(isolated_database):
    from backend.app.core.profile_versioning import ensure_profile_version
    profile = {"target_role": "Backend Engineer", "skills": ["Python"], "raw_cv_text": "CV v1"}
    assert ensure_profile_version(profile) == 1
    assert ensure_profile_version(profile) == 1
    assert ensure_profile_version({**profile, "raw_cv_text": "CV v2"}) == 2


def test_saved_search_persists_alert_for_new_matching_job(isolated_database, monkeypatch):
    from backend.app.modules.scrape import saved_search_service
    connection = __import__("backend.app.core.database", fromlist=["get_db_connection"]).get_db_connection()
    try:
        connection.cursor().execute("INSERT INTO saved_searches(id, name, queries_json, min_match_score) VALUES ('saved-one', 'Backend', '[\"Backend Engineer\"]', 70)")
        connection.commit()
    finally:
        connection.close()
    job = {"id": "new-job", "title": "Backend Engineer", "company": "Example", "match_score": 88}

    def add_job(**_kwargs):
        conn = __import__("backend.app.core.database", fromlist=["get_db_connection"]).get_db_connection()
        try:
            conn.cursor().execute("INSERT INTO scraped_jobs(id, title, company, platform, description) VALUES (?, ?, ?, ?, ?)",
                                  (job["id"], job["title"], job["company"], "remote", "A useful backend role."))
            conn.commit()
        finally:
            conn.close()
        return {"total_scraped": 1}

    monkeypatch.setattr(saved_search_service.unified_scraper, "run_multi_platform_scrape", add_job)
    monkeypatch.setattr(saved_search_service, "rank_and_save_all_jobs", lambda _profile: [job])
    result = saved_search_service.run_saved_search("saved-one")
    assert result["new_matches"] == 1
    conn = __import__("backend.app.core.database", fromlist=["get_db_connection"]).get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT title, body FROM user_notifications")
        notice = cursor.fetchone()
        assert notice["title"] == "Backend: yeni uygun ilanlar"
        assert "88" in notice["body"]
    finally:
        conn.close()
