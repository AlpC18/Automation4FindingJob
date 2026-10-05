#!/usr/bin/env python3
"""Safely restore the app's persisted local encryption key into its private .env."""

import os
import sqlite3
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
KEY_FILE = ROOT / "backend" / "data" / ".app_encryption_key"
DATABASE = ROOT / "backend" / "data" / "career_engine.db"


def main() -> None:
    if not ENV_FILE.is_file() or not KEY_FILE.is_file() or not DATABASE.is_file():
        raise SystemExit(".env, yerel anahtar ve veritabanının tamamı bulunmalı; hiçbir dosya değiştirilmedi.")

    key = KEY_FILE.read_bytes().strip()
    decryptor = Fernet(key)
    with sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "SELECT encrypted_token FROM job_source_settings WHERE encrypted_token LIKE 'fernet$%'"
        ).fetchall()
    try:
        for (value,) in rows:
            decryptor.decrypt(value[7:].encode("ascii"))
    except Exception as exc:
        raise SystemExit("Korunmuş yerel anahtar mevcut Apify verisini doğrulayamadı; hiçbir dosya değiştirilmedi.") from exc

    content = ENV_FILE.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    found = False
    for index, line in enumerate(lines):
        if line.startswith("APP_ENCRYPTION_KEY="):
            lines[index] = f"APP_ENCRYPTION_KEY={key.decode('ascii')}\n"
            found = True
            break
    if not found:
        raise SystemExit(".env içinde APP_ENCRYPTION_KEY alanı yok; hiçbir dosya değiştirilmedi.")

    descriptor, temporary_name = tempfile.mkstemp(prefix=".env.restore.", dir=ROOT)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.writelines(lines)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_name, ENV_FILE)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)

    print(f".env anahtarı korunan yerel anahtarla eşitlendi; {len(rows)} şifreli Apify kaydı doğrulandı. Anahtar yazdırılmadı.")


if __name__ == "__main__":
    main()
