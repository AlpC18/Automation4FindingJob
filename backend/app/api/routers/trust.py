"""Tenant-scoped user feedback for job and company reliability."""

import re
import unicodedata
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.core.database import get_db_connection

FeedbackType = Literal[
    "company_suspicious",
    "company_positive",
    "salary_mismatch",
    "salary_consistent",
    "salary_outdated",
    "listing_closed",
    "source_unavailable",
]

router = APIRouter()
CONTRADICTORY_FEEDBACK = {
    "company_suspicious": "company_positive",
    "company_positive": "company_suspicious",
    "salary_mismatch": "salary_consistent",
    "salary_consistent": "salary_mismatch",
}


def _ensure_feedback_table(conn) -> None:
    """Upgrade already-provisioned tenant databases on first feature use."""
    conn.cursor().execute("""
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
        )
    """)
    conn.commit()


class FeedbackRequest(BaseModel):
    company: str = Field(min_length=1, max_length=300)
    feedback_type: FeedbackType
    job_id: Optional[str] = Field(default=None, max_length=200)
    source_url: Optional[str] = Field(default="", max_length=2000)
    note: str = Field(default="", max_length=2000)


def _company_key(company: str) -> str:
    normalized = unicodedata.normalize("NFKC", company).casefold().strip()
    return re.sub(r"\s+", " ", normalized)


def _subject(req_job_id: Optional[str], company: str) -> tuple[str, str]:
    if req_job_id:
        return "job", f"job:{req_job_id}"
    return "company", f"company:{_company_key(company)}"


@router.get("/trust/feedback")
def get_feedback(
    job_id: Optional[str] = Query(default=None, max_length=200),
    company: Optional[str] = Query(default=None, max_length=300),
):
    if not job_id and not (company and company.strip()):
        raise HTTPException(status_code=422, detail="Provide a job_id or company.")
    subject_type, subject_key = _subject(job_id, company or "")
    conn = get_db_connection()
    try:
        _ensure_feedback_table(conn)
        rows = conn.cursor().execute(
            "SELECT id, subject_type, job_id, company, source_url, feedback_type, note, created_at, updated_at "
            "FROM company_feedback WHERE subject_key = ? ORDER BY updated_at DESC",
            (subject_key,),
        ).fetchall()
        items = [dict(row) for row in rows]
        return {
            "subject_type": subject_type,
            "feedback": items,
            "feedback_types": [item["feedback_type"] for item in items],
            "scope": "your_account_only",
        }
    finally:
        conn.close()


@router.post("/trust/feedback")
def save_feedback(req: FeedbackRequest):
    company = req.company.strip()
    if not company:
        raise HTTPException(status_code=422, detail="Company name is required.")

    source_url = (req.source_url or "").strip()
    if req.job_id:
        conn = get_db_connection()
        try:
            _ensure_feedback_table(conn)
            job = conn.cursor().execute(
                "SELECT company, url FROM scraped_jobs WHERE id = ?", (req.job_id,)
            ).fetchone()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found.")
            company = job["company"]
            source_url = source_url or job["url"] or ""
            subject_type, subject_key = _subject(req.job_id, company)
            opposite = CONTRADICTORY_FEEDBACK.get(req.feedback_type)
            if opposite:
                conn.cursor().execute(
                    "DELETE FROM company_feedback WHERE subject_key = ? AND feedback_type = ?",
                    (subject_key, opposite),
                )
            conn.cursor().execute(
                "INSERT INTO company_feedback (id, subject_key, subject_type, job_id, company, source_url, feedback_type, note) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(subject_key, feedback_type) DO UPDATE SET "
                "company = excluded.company, source_url = excluded.source_url, note = excluded.note, updated_at = CURRENT_TIMESTAMP",
                (uuid.uuid4().hex, subject_key, subject_type, req.job_id, company, source_url, req.feedback_type, req.note.strip()),
            )
            conn.commit()
        finally:
            conn.close()
    else:
        subject_type, subject_key = _subject(None, company)
        conn = get_db_connection()
        try:
            _ensure_feedback_table(conn)
            opposite = CONTRADICTORY_FEEDBACK.get(req.feedback_type)
            if opposite:
                conn.cursor().execute(
                    "DELETE FROM company_feedback WHERE subject_key = ? AND feedback_type = ?",
                    (subject_key, opposite),
                )
            conn.cursor().execute(
                "INSERT INTO company_feedback (id, subject_key, subject_type, company, source_url, feedback_type, note) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(subject_key, feedback_type) DO UPDATE SET "
                "company = excluded.company, source_url = excluded.source_url, note = excluded.note, updated_at = CURRENT_TIMESTAMP",
                (uuid.uuid4().hex, subject_key, subject_type, company, source_url, req.feedback_type, req.note.strip()),
            )
            conn.commit()
        finally:
            conn.close()

    return {"status": "saved", "feedback_type": req.feedback_type, "scope": "your_account_only"}


@router.delete("/trust/feedback/{feedback_type}")
def delete_feedback(
    feedback_type: FeedbackType,
    job_id: Optional[str] = Query(default=None, max_length=200),
    company: Optional[str] = Query(default=None, max_length=300),
):
    if not job_id and not (company and company.strip()):
        raise HTTPException(status_code=422, detail="Provide a job_id or company.")
    _, subject_key = _subject(job_id, company or "")
    conn = get_db_connection()
    try:
        _ensure_feedback_table(conn)
        conn.cursor().execute(
            "DELETE FROM company_feedback WHERE subject_key = ? AND feedback_type = ?",
            (subject_key, feedback_type),
        )
        conn.commit()
    finally:
        conn.close()
    return {"status": "deleted", "feedback_type": feedback_type, "scope": "your_account_only"}
