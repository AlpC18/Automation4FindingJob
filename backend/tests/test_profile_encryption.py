import sqlite3

from backend.app.api import profile as profile_api
from backend.app.core import profile_versioning


PROFILE_SCHEMA = """
CREATE TABLE candidate_profile (
 id INTEGER PRIMARY KEY, full_name TEXT, email TEXT, phone TEXT, location TEXT,
 target_role TEXT, years_of_experience INTEGER, skills_json TEXT, experience_json TEXT,
 education_json TEXT, raw_cv_text TEXT, clean_ats_cv_text TEXT, work_preference TEXT,
 languages_json TEXT, github_url TEXT, summary TEXT, work_style TEXT, writing_tone TEXT,
 style_profile_json TEXT, target_categories_json TEXT, target_roles_json TEXT
);
CREATE TABLE profile_revisions (
 version INTEGER PRIMARY KEY, fingerprint TEXT, target_role TEXT,
 profile_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _database(tmp_path, monkeypatch):
    path = tmp_path / "profile.sqlite3"
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(PROFILE_SCHEMA)
    connection.commit()
    connection.close()

    def connect():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(profile_api, "get_db_connection", connect)
    monkeypatch.setattr(profile_versioning, "get_db_connection", connect)
    return connect


def test_profile_values_are_encrypted_and_decoded_for_app(tmp_path, monkeypatch):
    connect = _database(tmp_path, monkeypatch)
    encoded_name, encoded_cv = profile_api.encrypt_profile_values(("Ada Example", "Resume text"))
    assert encoded_name.startswith("fernet$")
    assert encoded_cv.startswith("fernet$")

    conn = connect()
    conn.execute(
        "INSERT INTO candidate_profile(id, full_name, raw_cv_text, skills_json) VALUES (1, ?, ?, ?)",
        (encoded_name, encoded_cv, profile_api.encrypt_profile_values(("[\"Python\"]",))[0]),
    )
    conn.commit()
    conn.close()

    result = profile_api.fetch_candidate_profile()
    assert result["full_name"] == "Ada Example"
    assert result["raw_cv_text"] == "Resume text"
    assert result["skills"] == ["Python"]


def test_legacy_plaintext_profile_is_migrated_on_read(tmp_path, monkeypatch):
    connect = _database(tmp_path, monkeypatch)
    conn = connect()
    conn.execute("INSERT INTO candidate_profile(id, full_name, email) VALUES (1, 'Old Name', 'old@example.test')")
    conn.commit()
    conn.close()

    profile_api.fetch_candidate_profile()

    conn = connect()
    saved = conn.execute("SELECT full_name, email FROM candidate_profile WHERE id=1").fetchone()
    conn.close()
    assert saved["full_name"].startswith("fernet$")
    assert saved["email"].startswith("fernet$")


def test_profile_revision_snapshot_is_encrypted_at_rest(tmp_path, monkeypatch):
    connect = _database(tmp_path, monkeypatch)
    version = profile_versioning.ensure_profile_version(
        {"full_name": "Private Person", "target_role": "Engineer", "skills": ["Python"]}
    )

    conn = connect()
    stored = conn.execute("SELECT profile_json FROM profile_revisions WHERE version=?", (version,)).fetchone()[0]
    conn.close()
    assert stored.startswith("fernet$")
    assert "Python" not in stored
    assert profile_versioning.list_profile_revisions()[0]["profile"]["skills"] == ["Python"]
