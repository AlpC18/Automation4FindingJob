"""
Database and Local Persistence Layer
Stores Candidate Profiles, Scraped Jobs, Applications (Kanban), Form Memory, and Account Health.
"""

import json
import re
import sqlite3
from contextlib import contextmanager
from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.app.core.config import settings
from backend.app.core.tenant import get_tenant_id, reset_tenant_id, set_tenant_id

def is_postgres_database() -> bool:
    return settings.DATABASE_URL.startswith(("postgresql://", "postgres://", "postgresql+psycopg://"))


class _PostgresCursor:
    """Small qmark-to-psycopg adapter for the existing repository layer."""

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query: str, params=None):
        normalized = query
        if normalized.lstrip().upper().startswith("PRAGMA"):
            return self
        normalized = normalized.replace("?", "%s")
        if "AUTOINCREMENT" in normalized.upper():
            normalized = re.sub(
                r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
                "SERIAL PRIMARY KEY",
                normalized,
                flags=re.IGNORECASE,
            )
        self._cursor.execute(normalized, params or ())
        return self

    def executemany(self, query: str, params):
        self._cursor.executemany(query.replace("?", "%s"), params)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def lastrowid(self):
        return getattr(self._cursor, "lastrowid", None)


class _PostgresConnection:
    def __init__(self):
        import psycopg
        from psycopg.rows import dict_row

        dsn = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)
        self._connection = psycopg.connect(dsn, row_factory=dict_row)

    def cursor(self):
        return _PostgresCursor(self._connection.cursor())

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


def _connect_database(tenant_id: Optional[str] = None):
    if is_postgres_database():
        conn = _PostgresConnection()
        if tenant_id:
            schema = f"tenant_{re.sub(r'[^a-zA-Z0-9]', '', tenant_id)}"
            conn.cursor().execute(f'SET search_path TO "{schema}"')
        return conn
    if tenant_id:
        tenant_dir = settings.DATA_PATH / "tenants"
        tenant_dir.mkdir(parents=True, exist_ok=True)
        database_path = tenant_dir / f"{re.sub(r'[^a-zA-Z0-9]', '', tenant_id)}.db"
    else:
        database_path = settings.DATA_PATH / "career_engine.db"
    conn = sqlite3.connect(database_path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.row_factory = sqlite3.Row
    return conn


def get_db_connection():
    return _connect_database(get_tenant_id())


def get_control_db_connection():
    """Connect to the shared identity database regardless of request tenant."""
    return _connect_database(None)


def init_db(connection=None):
    owns_connection = connection is None
    conn = connection or get_db_connection()
    cursor = conn.cursor()

    if is_postgres_database():
        # pgvector is installed by the production image; the extension is
        # optional so managed Postgres instances without admin privileges can
        # still run the relational part of the application.
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.commit()
        except Exception:
            conn.rollback()
    
    # 1. Candidate Profile & Stylometry
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidate_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT,
        email TEXT,
        phone TEXT,
        location TEXT,
        target_role TEXT,
        years_of_experience INTEGER DEFAULT 0,
        skills_json TEXT DEFAULT '[]',
        experience_json TEXT DEFAULT '[]',
        education_json TEXT DEFAULT '[]',
        raw_cv_text TEXT DEFAULT '',
        clean_ats_cv_text TEXT DEFAULT '',
        style_profile_json TEXT DEFAULT '{}',
        follow_up_email_reminders INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidate_projects (
        id TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Dynamic CV Interview Missing Items
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cv_interview_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        category TEXT, -- e.g. 'project_metric', 'certifications', 'gap'
        answer TEXT DEFAULT '',
        status TEXT DEFAULT 'PENDING', -- PENDING, ANSWERED
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Form Memory Store (Easy Apply and custom portal dynamic questions)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS form_memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_normalized TEXT UNIQUE NOT NULL,
        original_question TEXT NOT NULL,
        answer TEXT NOT NULL,
        confidence REAL DEFAULT 1.0,
        requires_human_review INTEGER DEFAULT 0,
        times_used INTEGER DEFAULT 1,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Scraped Jobs & Ghost Job Analysis
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scraped_jobs (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        company TEXT NOT NULL,
        platform TEXT NOT NULL, -- linkedin, upwork, kosovajob, remoteok, etc.
        url TEXT,
        location TEXT,
        remote_type TEXT DEFAULT 'Unknown',
        salary_range TEXT DEFAULT 'Not disclosed',
        description TEXT NOT NULL,
        posted_date TEXT,
        ghost_score REAL DEFAULT 0.0, -- 0-100 (high means likely ghost job)
        ghost_reasons TEXT DEFAULT '[]',
        match_score REAL DEFAULT 0.0, -- 0-100 ATS Score
        match_tier TEXT DEFAULT 'Low', -- High, Medium, Low
        match_status TEXT DEFAULT 'Pass', -- Pass or Fail
        red_flags TEXT DEFAULT '[]',
        skill_gaps TEXT DEFAULT '[]',
        salary_benchmark_json TEXT DEFAULT '{}',
        status TEXT DEFAULT 'Draft', -- Draft, Human Review, Applied, Interview, Offer, Rejected
        human_texture_score REAL DEFAULT 0.0,
        cover_letter TEXT DEFAULT '',
        micro_portfolio TEXT DEFAULT '',
        cold_outreach_dork TEXT DEFAULT '',
        cold_outreach_msg TEXT DEFAULT '',
        applied_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Application execution is deliberately separate from the Kanban stage:
    # moving a card is a workflow action, while submission_confirmed means a
    # real external portal accepted the application.
    # 5. Account Health and Rate Limiting
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS account_activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL,
        action_type TEXT NOT NULL, -- apply, message, scrape
        status TEXT NOT NULL,      -- SUCCESS, BLOCKED, RATE_LIMITED
        target_info TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 6. Follow-up Reminders
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS follow_up_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        due_day INTEGER NOT NULL, -- 4, 9, or 14 day reminder
        scheduled_date TEXT NOT NULL,
        draft_email TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING', -- PENDING, SENT, CANCELLED
        email_notified_at TIMESTAMP,
        email_claimed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 7. Incoming Employer Inbox & Auto-Scheduler
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inbox_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT,
        sender_email TEXT NOT NULL,
        sender_name TEXT,
        subject TEXT NOT NULL,
        body_text TEXT NOT NULL,
        classification TEXT NOT NULL, -- REJECTION, INTERVIEW_INVITE, TECHNICAL_ASSESSMENT, ADDITIONAL_INFO
        detected_meet_url TEXT,
        proposed_reply TEXT,
        status TEXT DEFAULT 'UNREAD', -- UNREAD, REPLIED, ARCHIVED
        received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)


    # 8. Telegram Bot Dispatches & Mobile Command Events
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS telegram_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL, -- BRIEFING, INSTANT_ALERT, USER_COMMAND
        message_text TEXT NOT NULL,
        chat_id TEXT,
        status TEXT DEFAULT 'SENT',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 9. Official OAuth2 Connected Accounts (Google & Microsoft)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS oauth_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider TEXT UNIQUE NOT NULL, -- google, microsoft
        account_email TEXT NOT NULL,
        access_token TEXT NOT NULL,
        refresh_token TEXT,
        token_type TEXT DEFAULT 'Bearer',
        expires_at TIMESTAMP,
        scope TEXT,
        status TEXT DEFAULT 'ACTIVE', -- ACTIVE, REVOKED, EXPIRED
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 10. LinkedIn Session & Handshake Metadata
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS linkedin_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        is_synced INTEGER DEFAULT 0,
        has_li_at INTEGER DEFAULT 0,
        cookie_count INTEGER DEFAULT 0,
        raw_cookie_preview TEXT,
        last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 11. Canonical seen-job tracker (JSON payload keeps the schema portable)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS seen_jobs (
        id TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # User-submitted company/job reliability feedback, isolated with the tenant DB.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS company_feedback (
        id TEXT PRIMARY KEY,
        subject_key TEXT NOT NULL,
        subject_type TEXT NOT NULL,
        job_id TEXT NOT NULL DEFAULT '',
        company TEXT NOT NULL,
        source_url TEXT NOT NULL DEFAULT '',
        feedback_type TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(subject_key, feedback_type)
    );
    """)

    from backend.app.core.migrations import apply_migrations
    apply_migrations(conn, cursor)

    conn.commit()
    if owns_connection:
        conn.close()


def init_tenant_db(tenant_id: str):
    """Provision a fully isolated app schema or SQLite database for one user."""
    if is_postgres_database():
        control = get_control_db_connection()
        schema = f"tenant_{re.sub(r'[^a-zA-Z0-9]', '', tenant_id)}"
        control.cursor().execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        control.commit()
        control.close()
    token = set_tenant_id(tenant_id)
    try:
        init_db()
    finally:
        reset_tenant_id(token)


def init_auth_db():
    """Create the shared account table outside tenant-specific storage."""
    conn = get_control_db_connection()
    conn.cursor().execute(
        """
        CREATE TABLE IF NOT EXISTS auth_users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            email_verified INTEGER NOT NULL DEFAULT 1,
            session_version INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_schema_migrations (
            revision TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("SELECT revision FROM auth_schema_migrations")
    applied = {row["revision"] if isinstance(row, dict) else row[0] for row in cursor.fetchall()}
    if "0001_auth_security" not in applied:
        for column, definition in (
            ("email_verified", "INTEGER NOT NULL DEFAULT 1"),
            ("session_version", "INTEGER NOT NULL DEFAULT 0"),
        ):
            if is_postgres_database():
                cursor.execute(f"ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS {column} {definition}")
            else:
                cursor.execute("PRAGMA table_info(auth_users)")
                columns = {row[1] for row in cursor.fetchall()}
                if column not in columns:
                    cursor.execute(f"ALTER TABLE auth_users ADD COLUMN {column} {definition}")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth_security_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                purpose TEXT NOT NULL,
                expires_at REAL NOT NULL,
                used_at REAL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_tokens_user ON auth_security_tokens(user_id, purpose)")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth_login_attempts (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                succeeded INTEGER NOT NULL DEFAULT 0,
                attempted_at REAL NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_login_attempts_ip ON auth_login_attempts(ip_address, attempted_at)")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth_security_requests (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                purpose TEXT NOT NULL,
                requested_at REAL NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_security_requests_email ON auth_security_requests(email, requested_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_security_requests_ip ON auth_security_requests(ip_address, requested_at)")
        cursor.execute("INSERT INTO auth_schema_migrations(revision) VALUES (?)", ("0001_auth_security",))
    conn.commit()
    conn.close()


@contextmanager
def use_tenant(tenant_id: str):
    token = set_tenant_id(tenant_id)
    try:
        yield
    finally:
        reset_tenant_id(token)


# Several legacy modules initialize seed memory during import; retain this
# bootstrap until those initializers move behind the application lifespan.
init_db()
init_auth_db()
