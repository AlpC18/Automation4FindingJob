"""Regression coverage for public API contracts added during hardening."""

import sys
from types import SimpleNamespace

import pytest

from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.core.database import get_db_connection, init_db
from backend.app.main import app
from backend.app.api.routers import scrape as scrape_router


client = TestClient(app)


def test_saved_apify_tokens_reveal_only_in_local_nonproduction(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(scrape_router, "get_source_config", lambda _source: {"api_tokens": ["local-test-token"]})
    response = client.post("/api/scrape/sources/linkedin/tokens/reveal")
    assert response.status_code == 200
    assert response.json() == {"tokens": ["local-test-token"]}
    assert "no-store" in response.headers["cache-control"]

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    denied = client.post("/api/scrape/sources/linkedin/tokens/reveal")
    assert denied.status_code == 403


def test_api_key_protects_http_and_websocket(monkeypatch):
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "contract-secret")
    try:
        assert client.get("/").status_code == 401
        assert client.get("/", headers={"X-API-Key": "contract-secret"}).status_code == 200
        with client.websocket_connect("/api/ws/events?api_key=contract-secret") as websocket:
            assert websocket.receive_json()["type"] == "connection_established"
            websocket.send_text("ping")
            assert websocket.receive_text() == "pong"
    finally:
        monkeypatch.setattr(settings, "API_AUTH_TOKEN", "")


def test_authenticated_cors_preflight_is_handled_by_cors_layer(monkeypatch):
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "cors-secret")
    try:
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-API-Key",
            },
        )
        assert response.status_code in {200, 204}
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert "X-API-Key" in response.headers["access-control-allow-headers"]
    finally:
        monkeypatch.setattr(settings, "API_AUTH_TOKEN", "")


def test_runtime_configuration_is_public_and_secret_free(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "contract")
    monkeypatch.setattr(settings, "PUBLIC_API_URL", "https://api.example.test/api")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "should-not-leak")
    response = client.get("/api/system/runtime-config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["environment"] == "contract"
    assert payload["api"]["public_url"] == "https://api.example.test/api"
    assert "OPENAI_API_KEY" not in str(payload)


def test_career_preferences_persist_in_profile_and_survive_legacy_updates(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATA_PATH", tmp_path)
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'career_engine.db'}")
    monkeypatch.setattr(settings, "DEMO_DATA_ENABLED", False)
    init_db()

    payload = {
        "full_name": "Test Candidate",
        "email": "candidate@example.test",
        "target_role": "Data Analyst",
        "target_categories": ["Veri ve analitik"],
        "target_roles": ["Data Analyst", "Analytics Engineer"],
        "years_of_experience": 3,
        "skills": ["SQL", "Python"],
    }
    saved = client.post("/api/setup/update_profile", json=payload)
    assert saved.status_code == 200

    updated = client.get("/api/setup/profile").json()["profile"]
    assert updated["target_categories"] == ["Veri ve analitik"]
    assert updated["target_roles"] == ["Data Analyst", "Analytics Engineer"]

    legacy_update = {**payload, "target_role": "Senior Data Analyst"}
    legacy_update.pop("target_categories")
    legacy_update.pop("target_roles")
    assert client.post("/api/setup/update_profile", json=legacy_update).status_code == 200
    persisted = client.get("/api/setup/profile").json()["profile"]
    assert persisted["target_categories"] == ["Veri ve analitik"]
    assert persisted["target_roles"] == ["Senior Data Analyst"]


def test_llm_credentials_are_encrypted_and_never_returned(monkeypatch, tmp_path):
    from backend.app.core.security import generate_encryption_key

    monkeypatch.setattr(settings, "DATA_PATH", tmp_path)
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'career_engine.db'}")
    monkeypatch.setattr(settings, "APP_ENCRYPTION_KEY", generate_encryption_key())
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    init_db()

    secret = "sk-test-credential-never-return-this"
    saved = client.put("/api/llm/credentials", json={"provider": "openai", "api_key": secret})
    assert saved.status_code == 200
    assert secret not in saved.text

    status = client.get("/api/llm/credentials")
    assert status.status_code == 200
    openai_status = next(item for item in status.json()["providers"] if item["provider"] == "openai")
    assert openai_status["is_configured"] is True
    assert openai_status["has_saved_key"] is True
    assert secret not in status.text

    conn = get_db_connection()
    try:
        stored = conn.cursor()
        stored.execute("SELECT encrypted_api_key FROM llm_provider_credentials WHERE provider = ?", ("openai",))
        ciphertext = stored.fetchone()[0]
        assert ciphertext.startswith("fernet$")
        assert secret not in ciphertext
    finally:
        conn.close()

    from backend.app.core.provider_credentials import get_provider_api_key
    assert get_provider_api_key("openai") == secret
    removed = client.delete("/api/llm/credentials/openai")
    assert removed.status_code == 200
    assert get_provider_api_key("openai") == ""


def test_system_health_exposes_database_and_daemon_checks(monkeypatch):
    monkeypatch.setattr(settings, "USE_CELERY", False)
    response = client.get("/api/system/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["checks"]["database"]["status"] == "healthy"
    assert payload["checks"]["redis"]["status"] == "disabled"
    assert "active_schedules" in payload["checks"]["daemon"]


def test_kanban_apply_keeps_external_submission_unconfirmed():
    job_id = "contract-submission-state-job"
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scraped_jobs WHERE id = ?", (job_id,))
        cursor.execute(
            """
            INSERT INTO scraped_jobs (id, title, company, platform, description, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, "Contract Engineer", "Contract Co", "test", "A contract test job", "Human Review"),
        )
        conn.commit()

        response = client.post(
            "/api/outcome/update_status",
            json={"job_id": job_id, "new_status": "Applied"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["submission_confirmed"] is False
        assert payload["application_execution_mode"] == "simulation"

        cursor.execute(
            "SELECT submission_state, submission_confirmed, applied_at FROM scraped_jobs WHERE id = ?",
            (job_id,),
        )
        row = cursor.fetchone()
        assert row["submission_state"] == "pending_confirmation"
        assert row["submission_confirmed"] == 0
        assert row["applied_at"] is None
    finally:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scraped_jobs WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()


def test_simulated_confirmation_does_not_schedule_real_followups():
    job_id = "contract-simulated-followup-job"
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scraped_jobs WHERE id = ?", (job_id,))
        cursor.execute("DELETE FROM follow_up_queue WHERE job_id = ?", (job_id,))
        cursor.execute(
            """
            INSERT INTO scraped_jobs (id, title, company, platform, description, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, "Simulation Engineer", "Simulation Co", "test", "A simulated test job", "Applied"),
        )
        conn.commit()

        response = client.post(
            "/api/outcome/confirm_submission",
            json={
                "job_id": job_id,
                "execution_mode": "simulation",
                "message": "Test-only simulation confirmation",
            },
        )
        assert response.status_code == 200
        assert response.json()["application_execution_mode"] == "simulation"

        cursor.execute("SELECT COUNT(*) AS count FROM follow_up_queue WHERE job_id = ?", (job_id,))
        assert cursor.fetchone()["count"] == 0
    finally:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM follow_up_queue WHERE job_id = ?", (job_id,))
        cursor.execute("DELETE FROM scraped_jobs WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()


def test_kanban_status_broadcast_reaches_websocket_client():
    job_id = "contract-kanban-websocket-job"
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scraped_jobs WHERE id = ?", (job_id,))
        cursor.execute(
            """
            INSERT INTO scraped_jobs (id, title, company, platform, description, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, "Realtime Engineer", "Realtime Co", "test", "A websocket test job", "Draft"),
        )
        conn.commit()

        with client.websocket_connect("/api/ws/events") as websocket:
            assert websocket.receive_json()["type"] == "connection_established"
            response = client.post(
                "/api/outcome/update_status",
                json={"job_id": job_id, "new_status": "Interview"},
            )
            assert response.status_code == 200
            event = websocket.receive_json()
            assert event["type"] == "kanban_stage_changed"
            assert event["data"]["job_id"] == job_id
            assert event["data"]["new_status"] == "Interview"
    finally:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scraped_jobs WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()


@pytest.mark.asyncio
async def test_oauth_inbox_sync_deduplicates_external_message(monkeypatch):
    from backend.app.modules.outcome.oauth_mail_agent import oauth_mail_agent

    provider = "google"
    external_id = "google:contract-dedup-message"
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM oauth_accounts WHERE provider = ?", (provider,))
        cursor.execute(
            "DELETE FROM inbox_messages WHERE source_provider = ? AND external_message_id = ?",
            (provider, external_id),
        )
        conn.commit()

        oauth_mail_agent._save_oauth_account(
            provider=provider,
            email="contract@example.com",
            access_token="live-contract-token",
            refresh_token=None,
            expires_in=3600,
            scope="gmail.readonly",
        )

        async def fake_fetch(_token):
            return [{
                "external_message_id": external_id,
                "sender_email": "recruiter@contract.example",
                "sender_name": "Contract Recruiter",
                "subject": "Interview Invitation",
                "body_text": "Please schedule an interview at https://meet.google.com/abc-defg-hij",
            }]

        monkeypatch.setattr(oauth_mail_agent, "_fetch_gmail_messages", fake_fetch)
        first = await oauth_mail_agent.sync_emails(provider)
        second = await oauth_mail_agent.sync_emails(provider)
        assert first["synced_count"] == 1
        assert first["new_count"] == 1
        assert second["synced_count"] == 1
        assert second["new_count"] == 0
        assert second["duplicate_count"] == 1
    finally:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM oauth_accounts WHERE provider = ?", (provider,))
        cursor.execute(
            "DELETE FROM inbox_messages WHERE source_provider = ? AND external_message_id = ?",
            (provider, external_id),
        )
        conn.commit()
        conn.close()


def test_jobs_endpoint_decodes_json_columns_when_rows_exist():
    job_id = "contract-json-job"
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scraped_jobs WHERE id = ?", (job_id,))
        cursor.execute(
            """
            INSERT INTO scraped_jobs (
                id, title, company, platform, description,
                ghost_reasons, red_flags, skill_gaps, salary_benchmark_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, "JSON Engineer", "JSON Co", "test", "A test job", "[]", "[]", "[]", "{}"),
        )
        conn.commit()
        response = client.get("/api/scrape/jobs")
        assert response.status_code == 200
        assert any(job["id"] == job_id for job in response.json()["jobs"])
    finally:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scraped_jobs WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()


def test_secret_encryption_round_trip(monkeypatch):
    from backend.app.core.security import decrypt_secret, encrypt_secret, generate_encryption_key

    monkeypatch.setattr(settings, "APP_ENCRYPTION_KEY", generate_encryption_key())
    plaintext = "oauth-refresh-token"
    encrypted = encrypt_secret(plaintext)
    assert encrypted.startswith("fernet$")
    assert encrypted != plaintext
    assert decrypt_secret(encrypted) == plaintext
