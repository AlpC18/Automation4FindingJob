"""The candidate's own CV file, kept encrypted so it never has to be uploaded twice."""

import base64
import hashlib
from typing import Any, Dict, Optional

from backend.app.core.database import get_db_connection
from backend.app.core.security import decrypt_secret, encrypt_secret

METADATA_COLUMNS = "filename, content_type, size_bytes, content_hash, page_count, uploaded_at"
# Facts a CV can supply. A value the user already saved always wins over the CV's.
SCALAR_FIELDS = ("full_name", "email", "phone", "location", "target_role", "github_url", "summary")
LIST_FIELDS = ("skills", "languages")
RECORD_FIELDS = ("experience", "education")
# Without these the ranking and the drafts have nothing to work from.
ESSENTIAL_FIELDS = ("full_name", "email", "target_role", "skills")


def save_cv_document(filename: str, content_type: str, content: bytes, page_count: Optional[int]) -> Dict[str, Any]:
    """Keep one CV per workspace; a new upload replaces the previous file."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cv_documents")
        cursor.execute(
            "INSERT INTO cv_documents (id, filename, content_type, size_bytes, content_hash, page_count, encrypted_content) "
            "VALUES ('current', ?, ?, ?, ?, ?, ?)",
            (filename, content_type, len(content), hashlib.sha256(content).hexdigest(), page_count,
             encrypt_secret(base64.b64encode(content).decode("ascii"))),
        )
        conn.commit()
    finally:
        conn.close()
    return get_cv_metadata()


def get_cv_metadata() -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        row = conn.cursor().execute(f"SELECT {METADATA_COLUMNS} FROM cv_documents WHERE id = 'current'").fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def get_cv_file() -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        row = conn.cursor().execute("SELECT filename, content_type, encrypted_content FROM cv_documents WHERE id = 'current'").fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {"filename": row["filename"], "content_type": row["content_type"],
            "content": base64.b64decode(decrypt_secret(row["encrypted_content"]))}


def delete_cv_document() -> bool:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cv_documents")
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def merge_cv_into_profile(profile: Dict[str, Any], fields: Dict[str, Any], cv_text: str) -> tuple[Dict[str, Any], list[str]]:
    """Fill what the profile lacks from the CV. Returns the merged profile and the names of the fields it filled."""
    merged = dict(profile)
    filled = []
    for name in SCALAR_FIELDS:
        if not str(profile.get(name) or "").strip() and str(fields.get(name) or "").strip():
            merged[name] = fields[name]
            filled.append(name)
    if not profile.get("years_of_experience") and fields.get("years_of_experience"):
        merged["years_of_experience"] = fields["years_of_experience"]
        filled.append("years_of_experience")
    for name in LIST_FIELDS:
        existing = [str(item) for item in profile.get(name) or []]
        known = {item.lower() for item in existing}
        added = [str(item) for item in fields.get(name) or [] if str(item).lower() not in known]
        if added:
            merged[name] = existing + added
            filled.append(name)
    for name in RECORD_FIELDS:
        if not profile.get(name) and fields.get(name):
            merged[name] = fields[name]
            filled.append(name)
    merged["raw_cv_text"] = cv_text
    return merged, filled


def missing_essentials(profile: Dict[str, Any]) -> list[str]:
    return [name for name in ESSENTIAL_FIELDS if not profile.get(name)]
