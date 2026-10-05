import sqlite3

from backend.app.modules.outcome import kanban_manager as kanban_module


def test_kanban_hides_unprepared_feed_and_unconfirmed_interviews(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE scraped_jobs (
            id TEXT, status TEXT, stale_at TEXT, submission_confirmed INTEGER,
            cover_letter TEXT, micro_portfolio TEXT, match_score REAL
        )
        """
    )
    connection.executemany(
        "INSERT INTO scraped_jobs VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("raw-draft", "Draft", None, 0, None, None, 99),
            ("raw-new", "New", None, 0, None, None, 98),
            ("prepared-draft", "Draft", None, 0, "Tailored letter", None, 80),
            ("applied-pending", "Applied", None, 0, None, None, 70),
            ("unconfirmed-interview", "Interview", None, 0, None, None, 60),
            ("confirmed-interview", "Interview", None, 1, None, None, 50),
            ("unconfirmed-offer", "Offer", None, 0, None, None, 40),
            ("rejected", "Rejected", None, 0, None, None, 30),
        ],
    )
    monkeypatch.setattr(kanban_module, "get_db_connection", lambda: connection)

    board = kanban_module.KanbanManager().get_kanban_board()

    assert [row["id"] for row in board["Draft"]] == ["prepared-draft"]
    assert [row["id"] for row in board["Applied"]] == ["applied-pending"]
    assert [row["id"] for row in board["Interview"]] == ["confirmed-interview"]
    assert board["Offer"] == []
    assert [row["id"] for row in board["Rejected"]] == ["rejected"]
    connection.close()
