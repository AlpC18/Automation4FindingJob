import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.modules.outcome.telegram_bot import (
    get_telegram_settings,
    update_telegram_settings,
    send_job_alert,
)
from backend.app.core.database import get_db_connection

client = TestClient(app)


def test_telegram_settings_persistence():
    """Verify Telegram settings can be saved and retrieved."""
    updated = update_telegram_settings(
        bot_token="test-bot-token-123",
        chat_id="test-chat-456",
        is_enabled=True,
        min_match_score=80,
    )
    assert updated["bot_token"] == "test-bot-token-123"
    assert updated["chat_id"] == "test-chat-456"
    assert updated["is_enabled"] is True
    assert updated["min_match_score"] == 80

    fetched = get_telegram_settings()
    assert fetched["bot_token"] == "test-bot-token-123"
    assert fetched["is_enabled"] is True


def test_telegram_api_endpoints():
    """Test /api/system/telegram GET and POST."""
    res = client.get("/api/system/telegram")
    assert res.status_code == 200
    data = res.json()
    assert "bot_token" in data
    assert "is_enabled" in data

    post_res = client.post(
        "/api/system/telegram",
        json={
            "bot_token": "token-xyz",
            "chat_id": "12345",
            "is_enabled": False,
            "min_match_score": 85,
        },
    )
    assert post_res.status_code == 200
    assert post_res.json()["min_match_score"] == 85


def test_outreach_draft_endpoint():
    """Test generating cold outreach, Google X-Ray dork, and micro portfolio."""
    res = client.post(
        "/api/apply/outreach/draft",
        json={
            "company": "Stripe",
            "title": "Software Engineer",
            "location": "Remote",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["company"] == "Stripe"
    assert "google_search_url" in data
    assert "linkedin.com/in/" in data["dork_query"]
    assert "Stripe" in data["cold_outreach_message"]
    assert len(data["predicted_email_formats"]) > 0


def test_follow_up_cadence_endpoint():
    """Test generating 3-touch follow up messages."""
    conn = get_db_connection()
    conn.cursor().execute(
        "INSERT INTO scraped_jobs (id, title, company, platform, description) VALUES ('cadence-job', 'Full Stack Dev', 'Vercel', 'remote', 'Description of Vercel role') "
        "ON CONFLICT(id) DO NOTHING"
    )
    conn.commit()
    conn.close()

    try:
        res = client.get("/api/apply/jobs/cadence-job/follow_up_cadence")
        assert res.status_code == 200
        data = res.json()
        assert data["company"] == "Vercel"
        assert len(data["cadence"]) == 3
        stages = [touch["stage"] for touch in data["cadence"]]
        assert "Touch 1 (Day 4)" in stages[0]
    finally:
        conn = get_db_connection()
        conn.cursor().execute("DELETE FROM scraped_jobs WHERE id = 'cadence-job'")
        conn.commit()
        conn.close()


def test_predicted_questions_endpoint():
    """Test /api/interview/jobs/{id}/predicted_questions."""
    conn = get_db_connection()
    conn.cursor().execute(
        "INSERT INTO scraped_jobs (id, title, company, platform, description) VALUES ('quest-job', 'Backend Engineer', 'Google', 'remote', 'Go and Kubernetes description') "
        "ON CONFLICT(id) DO NOTHING"
    )
    conn.commit()
    conn.close()

    try:
        res = client.get("/api/interview/jobs/quest-job/predicted_questions")
        assert res.status_code == 200
        data = res.json()
        assert "questions" in data
        assert len(data["questions"]) > 0
    finally:
        conn = get_db_connection()
        conn.cursor().execute("DELETE FROM scraped_jobs WHERE id = 'quest-job'")
        conn.commit()
        conn.close()
