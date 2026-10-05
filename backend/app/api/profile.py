"""Shared candidate profile provider for API domain routers."""

import json
from typing import Any, Dict

from backend.app.core.database import get_db_connection
from backend.app.core.security import decrypt_secret, encrypt_secret


PROFILE_ENCRYPTED_COLUMNS = (
    "full_name", "email", "phone", "location", "skills_json", "experience_json",
    "education_json", "raw_cv_text", "clean_ats_cv_text", "style_profile_json",
    "languages_json", "github_url", "summary", "work_preference", "work_style",
    "writing_tone",
)


def encrypt_profile_values(values: tuple[Any, ...]) -> tuple[Any, ...]:
    """Encrypt profile field values before writing them to persistent storage."""
    return tuple(encrypt_secret(value) if isinstance(value, str) else value for value in values)


def fetch_candidate_profile() -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM candidate_profile ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        data = dict(row)
        migrated = {}
        for column in PROFILE_ENCRYPTED_COLUMNS:
            value = data.get(column)
            if value:
                plain = decrypt_secret(value)
                data[column] = plain
                if plain == value:
                    migrated[column] = encrypt_secret(plain)
        if migrated:
            assignments = ", ".join(f"{column} = ?" for column in migrated)
            cursor.execute(
                f"UPDATE candidate_profile SET {assignments} WHERE id = ?",
                (*migrated.values(), data["id"]),
            )
            conn.commit()
        conn.close()
        data["skills"] = json.loads(data["skills_json"] or "[]")
        data["experience"] = json.loads(data["experience_json"] or "[]")
        data["education"] = json.loads(data["education_json"] or "[]")
        data["style_profile"] = json.loads(data["style_profile_json"] or "{}")
        data["languages"] = json.loads(data.get("languages_json") or "[]")
        data["target_categories"] = json.loads(data.get("target_categories_json") or "[]")
        data["target_roles"] = json.loads(data.get("target_roles_json") or "[]")
        if not data["target_roles"] and data.get("target_role"):
            data["target_roles"] = [data["target_role"]]
        return data

    conn.close()

    return {
        "full_name": "",
        "email": "",
        "phone": "",
        "location": "",
        "target_role": "",
        "target_categories": [],
        "target_roles": [],
        "years_of_experience": 0,
        "skills": [],
        "experience": [],
        "education": [],
        "work_preference": "",
        "languages": [],
        "github_url": "",
        "summary": "",
        "work_style": "",
        "writing_tone": "",
        "raw_cv_text": "",
        "clean_ats_cv_text": "",
        "style_profile": {},
        "follow_up_email_reminders": False,
    }
