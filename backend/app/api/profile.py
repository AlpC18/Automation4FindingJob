"""Shared candidate profile provider for API domain routers, supporting multiple candidate profiles."""

import json
import uuid
from typing import Any, Dict, List, Optional

from backend.app.core.database import get_db_connection
from backend.app.core.security import decrypt_secret, encrypt_secret


PROFILE_ENCRYPTED_COLUMNS = (
    "full_name", "email", "phone", "location", "target_role", "skills_json", "experience_json",
    "education_json", "raw_cv_text", "clean_ats_cv_text", "style_profile_json",
    "languages_json", "github_url", "summary", "work_preference", "work_style",
    "writing_tone",
)


def encrypt_profile_values(values: tuple[Any, ...]) -> tuple[Any, ...]:
    """Encrypt profile field values before writing them to persistent storage."""
    return tuple(encrypt_secret(value) if isinstance(value, str) else value for value in values)


def _bootstrap_multi_profiles(conn, legacy_data: Dict[str, Any]) -> None:
    """Ensure candidate_profiles has at least one active profile based on legacy candidate_profile."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) AS total FROM candidate_profiles")
        count = cursor.fetchone()
        total = count["total"] if isinstance(count, dict) else (count[0] if count else 0)
        if total == 0 and legacy_data.get("full_name") or legacy_data.get("target_role"):
            profile_name = legacy_data.get("full_name") or legacy_data.get("target_role") or "Ana Profil"
            profile_id = f"prof-{uuid.uuid4().hex[:8]}"
            cursor.execute(
                """INSERT INTO candidate_profiles(
                    id, name, is_active, full_name, email, phone, location, target_role,
                    target_categories_json, target_roles_json, years_of_experience,
                    skills_json, experience_json, education_json, languages_json,
                    github_url, summary, work_preference, work_style, writing_tone,
                    raw_cv_text, clean_ats_cv_text
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    profile_id,
                    profile_name,
                    encrypt_secret(legacy_data.get("full_name", "")),
                    encrypt_secret(legacy_data.get("email", "")),
                    encrypt_secret(legacy_data.get("phone", "")),
                    encrypt_secret(legacy_data.get("location", "")),
                    encrypt_secret(legacy_data.get("target_role", "")),
                    legacy_data.get("target_categories_json", "[]"),
                    legacy_data.get("target_roles_json", "[]"),
                    legacy_data.get("years_of_experience", 0),
                    encrypt_secret(legacy_data.get("skills_json", "[]")),
                    encrypt_secret(legacy_data.get("experience_json", "[]")),
                    encrypt_secret(legacy_data.get("education_json", "[]")),
                    encrypt_secret(legacy_data.get("languages_json", "[]")),
                    encrypt_secret(legacy_data.get("github_url", "")),
                    encrypt_secret(legacy_data.get("summary", "")),
                    encrypt_secret(legacy_data.get("work_preference", "")),
                    encrypt_secret(legacy_data.get("work_style", "")),
                    encrypt_secret(legacy_data.get("writing_tone", "")),
                    encrypt_secret(legacy_data.get("raw_cv_text", "")),
                    encrypt_secret(legacy_data.get("clean_ats_cv_text", "")),
                ),
            )
            conn.commit()
    except Exception:
        # candidate_profiles table might be in migration
        pass


def fetch_candidate_profile() -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Try to fetch active profile from candidate_profiles
    try:
        cursor.execute("SELECT * FROM candidate_profiles WHERE is_active = 1 LIMIT 1")
        row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT * FROM candidate_profiles ORDER BY updated_at DESC LIMIT 1")
            row = cursor.fetchone()
        if row:
            data = dict(row)
            for column in PROFILE_ENCRYPTED_COLUMNS:
                value = data.get(column)
                if value:
                    data[column] = decrypt_secret(value)
            conn.close()
            data["skills"] = json.loads(data.get("skills_json") or "[]")
            data["experience"] = json.loads(data.get("experience_json") or "[]")
            data["education"] = json.loads(data.get("education_json") or "[]")
            data["style_profile"] = json.loads(data.get("style_profile_json") or "{}")
            data["languages"] = json.loads(data.get("languages_json") or "[]")
            data["target_categories"] = json.loads(data.get("target_categories_json") or "[]")
            data["target_roles"] = json.loads(data.get("target_roles_json") or "[]")
            if not data["target_roles"] and data.get("target_role"):
                data["target_roles"] = [data["target_role"]]
            return data
    except Exception:
        pass

    # 2. Fallback to legacy candidate_profile
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
        
        # Bootstrap into candidate_profiles if not yet done
        _bootstrap_multi_profiles(conn, data)
        conn.close()

        data["skills"] = json.loads(data.get("skills_json") or "[]")
        data["experience"] = json.loads(data.get("experience_json") or "[]")
        data["education"] = json.loads(data.get("education_json") or "[]")
        data["style_profile"] = json.loads(data.get("style_profile_json") or "{}")
        data["languages"] = json.loads(data.get("languages_json") or "[]")
        data["target_categories"] = json.loads(data.get("target_categories_json") or "[]")
        data["target_roles"] = json.loads(data.get("target_roles_json") or "[]")
        if not data["target_roles"] and data.get("target_role"):
            data["target_roles"] = [data["target_role"]]
        return data

    conn.close()

    return {
        "id": "default",
        "name": "Varsayılan Profil",
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


def list_candidate_profiles() -> List[Dict[str, Any]]:
    """List all candidate profiles in the system with their status."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM candidate_profiles ORDER BY is_active DESC, updated_at DESC")
        rows = cursor.fetchall()
        if not rows:
            # Check legacy and bootstrap
            fetch_candidate_profile()
            cursor.execute("SELECT * FROM candidate_profiles ORDER BY is_active DESC, updated_at DESC")
            rows = cursor.fetchall()
        profiles = []
        for row in rows:
            p = dict(row)
            profiles.append({
                "id": p["id"],
                "name": p["name"],
                "is_active": bool(p["is_active"]),
                "full_name": decrypt_secret(p["full_name"] or ""),
                "target_role": decrypt_secret(p["target_role"] or ""),
                "location": decrypt_secret(p["location"] or ""),
                "years_of_experience": p["years_of_experience"],
                "created_at": p["created_at"],
                "updated_at": p["updated_at"],
            })
        return profiles
    except Exception:
        return []
    finally:
        conn.close()


def activate_candidate_profile(profile_id: str) -> Dict[str, Any]:
    """Activate a candidate profile and sync to legacy table for total compatibility."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM candidate_profiles WHERE id = ?", (profile_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Profil bulunamadı.")
        
        target = dict(row)
        cursor.execute("UPDATE candidate_profiles SET is_active = 0")
        cursor.execute("UPDATE candidate_profiles SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (profile_id,))

        # Sync to legacy candidate_profile
        cursor.execute("DELETE FROM candidate_profile")
        cursor.execute(
            """INSERT INTO candidate_profile(
                full_name, email, phone, location, target_role,
                years_of_experience, skills_json, experience_json, education_json,
                raw_cv_text, clean_ats_cv_text, work_preference, languages_json,
                github_url, summary, work_style, writing_tone,
                target_categories_json, target_roles_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                target.get("full_name", ""),
                target.get("email", ""),
                target.get("phone", ""),
                target.get("location", ""),
                target.get("target_role", ""),
                target.get("years_of_experience", 0),
                target.get("skills_json", "[]"),
                target.get("experience_json", "[]"),
                target.get("education_json", "[]"),
                target.get("raw_cv_text", ""),
                target.get("clean_ats_cv_text", ""),
                target.get("work_preference", ""),
                target.get("languages_json", "[]"),
                target.get("github_url", ""),
                target.get("summary", ""),
                target.get("work_style", ""),
                target.get("writing_tone", ""),
                target.get("target_categories_json", "[]"),
                target.get("target_roles_json", "[]"),
            ),
        )
        conn.commit()
        return {"id": profile_id, "name": target["name"], "is_active": True}
    finally:
        conn.close()


def create_candidate_profile(name: str, target_role: str = "", full_name: str = "", initial_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create a new profile (e.g. for sister or friend)."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        profile_id = f"prof-{uuid.uuid4().hex[:8]}"
        data = initial_data or {}
        cursor.execute(
            """INSERT INTO candidate_profiles(
                id, name, is_active, full_name, email, phone, location, target_role,
                target_categories_json, target_roles_json, years_of_experience,
                skills_json, experience_json, education_json, languages_json,
                github_url, summary, work_preference, work_style, writing_tone,
                raw_cv_text, clean_ats_cv_text
            ) VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile_id,
                name.strip(),
                encrypt_secret(full_name.strip() or data.get("full_name", "")),
                encrypt_secret(data.get("email", "")),
                encrypt_secret(data.get("phone", "")),
                encrypt_secret(data.get("location", "")),
                encrypt_secret(target_role.strip() or data.get("target_role", "")),
                json.dumps(data.get("target_categories", [])),
                json.dumps([target_role.strip()] if target_role.strip() else data.get("target_roles", [])),
                data.get("years_of_experience", 0),
                encrypt_secret(json.dumps(data.get("skills", []))),
                encrypt_secret(json.dumps(data.get("experience", []))),
                encrypt_secret(json.dumps(data.get("education", []))),
                encrypt_secret(json.dumps(data.get("languages", []))),
                encrypt_secret(data.get("github_url", "")),
                encrypt_secret(data.get("summary", "")),
                encrypt_secret(data.get("work_preference", "")),
                encrypt_secret(data.get("work_style", "")),
                encrypt_secret(data.get("writing_tone", "")),
                encrypt_secret(data.get("raw_cv_text", "")),
                encrypt_secret(data.get("clean_ats_cv_text", "")),
            ),
        )
        conn.commit()
        return {"id": profile_id, "name": name.strip(), "target_role": target_role.strip()}
    finally:
        conn.close()


def delete_candidate_profile(profile_id: str) -> None:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT is_active FROM candidate_profiles WHERE id = ?", (profile_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Profil bulunamadı.")
        if row["is_active"] if isinstance(row, dict) else row[0]:
            raise ValueError("Aktif olan profil silinemez. Önce başka bir profili aktif yapın.")
        cursor.execute("DELETE FROM candidate_profiles WHERE id = ?", (profile_id,))
        conn.commit()
    finally:
        conn.close()
