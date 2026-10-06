"""The jobs feed can be asked for a short list plus counts, and id lookups survive a very large feed."""

from fastapi.testclient import TestClient

from backend.app.core.database import get_db_connection
from backend.app.main import app
from backend.app.modules.outcome.inbox_agent import inbox_agent
from backend.app.modules.outcome.job_workspace import get_job_flags_for_ids
from backend.app.modules.scrape.job_link_health import get_job_link_checks

client = TestClient(app)
JOBS = [
    ("feedprobe-a", 90, 0, "Draft"),
    ("feedprobe-b", 50, 60, "Draft"),
    ("feedprobe-c", 80, 0, "Applied"),
]


def test_limited_feed_returns_the_top_rows_and_counts_for_the_whole_feed():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scraped_jobs WHERE id LIKE 'feedprobe-%'")
        for job_id, match, ghost, status in JOBS:
            cursor.execute(
                "INSERT INTO scraped_jobs (id, title, company, platform, description, match_score, ghost_score, status) "
                "VALUES (?, 'Engineer', 'Feedprobe Ltd', 'test', 'A job', ?, ?, ?)",
                (job_id, match, ghost, status),
            )
        conn.commit()

        body = client.get("/api/scrape/jobs", params={"q": "feedprobe", "limit": 1}).json()

        assert [job["id"] for job in body["jobs"]] == ["feedprobe-a"]
        assert (body["total"], body["current_feed_total"]) == (3, 2)
        assert (body["ghost_total"], body["high_match_total"]) == (1, 1)
    finally:
        conn.cursor().execute("DELETE FROM scraped_jobs WHERE id LIKE 'feedprobe-%'")
        conn.commit()
        conn.close()


def test_id_lookups_accept_more_ids_than_one_sql_statement_allows():
    ids = [f"missing-{number}" for number in range(40_000)]

    assert get_job_flags_for_ids(ids) == {}
    assert get_job_link_checks(ids) == {}


def test_inbox_can_be_read_by_status():
    assert all(message["status"] == "UNREAD" for message in inbox_agent.get_all_messages(status="UNREAD"))
