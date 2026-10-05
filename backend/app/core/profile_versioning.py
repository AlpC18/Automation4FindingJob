"""Stable profile-version attribution shared by application drafts and analytics."""

import hashlib
import json
from typing import Any

from backend.app.core.database import get_db_connection
from backend.app.core.security import decrypt_secret, encrypt_secret


SNAPSHOT_FIELDS = (
    "target_role", "years_of_experience", "skills", "experience", "education",
    "work_preference", "languages", "summary", "target_categories", "target_roles",
)


def profile_fingerprint(profile: dict[str, Any]) -> str:
    fields = ("full_name", "target_role", "years_of_experience", "skills", "experience", "education", "raw_cv_text", "work_preference", "languages")
    stable = {key: profile.get(key) for key in fields}
    return hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def _profile_snapshot(profile: dict[str, Any]) -> dict[str, Any]:
    """Keep only approved career fields; never copy raw CV/contact secrets."""
    return {key: profile.get(key) for key in SNAPSHOT_FIELDS if profile.get(key) is not None}


def ensure_profile_version(profile: dict[str, Any]) -> int:
    fingerprint = profile_fingerprint(profile)
    snapshot = json.dumps(_profile_snapshot(profile), sort_keys=True, ensure_ascii=False, default=str)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT version, fingerprint FROM profile_revisions ORDER BY version DESC LIMIT 1")
        latest = cursor.fetchone()
        if latest and latest["fingerprint"] == fingerprint:
            return int(latest["version"])
        version = (int(latest["version"]) if latest else 0) + 1
        cursor.execute(
            "INSERT INTO profile_revisions(version, fingerprint, target_role, profile_json) VALUES (?, ?, ?, ?)",
            (version, fingerprint, profile.get("target_role") or "", encrypt_secret(snapshot)),
        )
        conn.commit()
        return version
    finally:
        conn.close()


def list_profile_revisions(limit: int = 20) -> list[dict[str, Any]]:
    conn = get_db_connection()
    try:
        rows = conn.cursor().execute(
            "SELECT version, target_role, profile_json, created_at FROM profile_revisions ORDER BY version DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                stored = item.pop("profile_json") or "{}"
                plain = decrypt_secret(stored)
                item["profile"] = json.loads(plain)
                if plain == stored:
                    conn.cursor().execute(
                        "UPDATE profile_revisions SET profile_json = ? WHERE version = ?",
                        (encrypt_secret(plain), item["version"]),
                    )
            except (TypeError, ValueError):
                item["profile"] = {}
            result.append(item)
        conn.commit()
        return result
    finally:
        conn.close()


def compare_profile_revisions(from_version: int, to_version: int) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        rows = conn.cursor().execute(
            "SELECT version, target_role, profile_json, created_at FROM profile_revisions WHERE version IN (?, ?)",
            (from_version, to_version),
        ).fetchall()
    finally:
        conn.close()
    by_version = {int(row["version"]): dict(row) for row in rows}
    if from_version not in by_version or to_version not in by_version:
        raise ValueError("Profil sürümü bulunamadı.")
    def decode(item: dict[str, Any]) -> dict[str, Any]:
        try:
            return json.loads(decrypt_secret(item.get("profile_json") or "{}"))
        except (TypeError, ValueError):
            return {}
    before, after = decode(by_version[from_version]), decode(by_version[to_version])
    keys = sorted(set(before) | set(after))
    changes = [
        {"field": key, "before": before.get(key), "after": after.get(key), "changed": before.get(key) != after.get(key)}
        for key in keys
    ]
    return {"from_version": from_version, "to_version": to_version, "changes": changes, "changed_count": sum(1 for item in changes if item["changed"])}
