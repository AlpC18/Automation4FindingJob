"""
Telegram Notification Bot Module
Sends real-time high-matching job alerts directly to candidate's Telegram.
First-Mover Advantage: alerts within minutes of new job postings.
"""

import logging
import urllib.parse
from typing import Any, Dict, Optional
import httpx

from backend.app.core.database import get_db_connection

logger = logging.getLogger(__name__)


def init_telegram_db():
    """Ensure telegram_settings table exists in database."""
    conn = get_db_connection()
    try:
        conn.cursor().execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                bot_token TEXT DEFAULT '',
                chat_id TEXT DEFAULT '',
                is_enabled INTEGER DEFAULT 0,
                min_match_score INTEGER DEFAULT 75,
                notify_on_new_jobs INTEGER DEFAULT 1,
                notify_on_interview INTEGER DEFAULT 1,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.cursor().execute(
            """
            INSERT OR IGNORE INTO telegram_settings (id, bot_token, chat_id, is_enabled, min_match_score)
            VALUES (1, '', '', 0, 75)
            """
        )
        conn.cursor().execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_alerted_jobs (
                job_id TEXT PRIMARY KEY,
                alerted_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


init_telegram_db()


def get_telegram_settings() -> Dict[str, Any]:
    """Retrieve stored Telegram notification settings."""
    conn = get_db_connection()
    try:
        row = conn.cursor().execute(
            "SELECT bot_token, chat_id, is_enabled, min_match_score, notify_on_new_jobs, notify_on_interview FROM telegram_settings WHERE id = 1"
        ).fetchone()
        if not row:
            return {
                "bot_token": "",
                "chat_id": "",
                "is_enabled": False,
                "min_match_score": 75,
                "notify_on_new_jobs": True,
                "notify_on_interview": True,
            }
        return {
            "bot_token": row["bot_token"] or "",
            "chat_id": row["chat_id"] or "",
            "is_enabled": bool(row["is_enabled"]),
            "min_match_score": int(row["min_match_score"] or 75),
            "notify_on_new_jobs": bool(row["notify_on_new_jobs"]),
            "notify_on_interview": bool(row["notify_on_interview"]),
        }
    finally:
        conn.close()


def update_telegram_settings(
    bot_token: str,
    chat_id: str,
    is_enabled: bool,
    min_match_score: int = 75,
    notify_on_new_jobs: bool = True,
    notify_on_interview: bool = True,
) -> Dict[str, Any]:
    """Update Telegram notification configuration."""
    conn = get_db_connection()
    try:
        conn.cursor().execute(
            """
            UPDATE telegram_settings
            SET bot_token = ?,
                chat_id = ?,
                is_enabled = ?,
                min_match_score = ?,
                notify_on_new_jobs = ?,
                notify_on_interview = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (
                bot_token.strip(),
                chat_id.strip(),
                1 if is_enabled else 0,
                max(0, min(100, int(min_match_score))),
                1 if notify_on_new_jobs else 0,
                1 if notify_on_interview else 0,
            ),
        )
        conn.commit()
        return get_telegram_settings()
    finally:
        conn.close()


def send_telegram_message(text: str, parse_mode: str = "HTML") -> bool:
    """Send a message using Telegram Bot API."""
    settings = get_telegram_settings()
    token = settings.get("bot_token")
    chat_id = settings.get("chat_id")

    if not token or not chat_id:
        logger.debug("Telegram credentials not configured; skipping alert.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("Telegram notification sent successfully.")
                return True
            else:
                logger.warning(f"Telegram API error {resp.status_code}: {resp.text}")
                return False
    except Exception as exc:
        logger.error(f"Failed to send Telegram message: {exc}")
        return False


def send_job_alert(job: Dict[str, Any], match_score: Optional[int] = None) -> bool:
    """Send a formatted job notification alert to Telegram."""
    settings = get_telegram_settings()
    if not settings.get("is_enabled"):
        return False

    score = match_score if match_score is not None else job.get("match_score", 0)
    min_score = settings.get("min_match_score", 75)

    if score < min_score:
        return False

    job_id = job.get("id")
    if job_id:
        conn = get_db_connection()
        try:
            exists = conn.cursor().execute("SELECT 1 FROM telegram_alerted_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if exists:
                return False
        finally:
            conn.close()

    title = job.get("title", "İsimsiz Pozisyon")
    company = job.get("company", "Bilinmeyen Şirket")
    location = job.get("location", "Belirtilmemiş")
    platform = (job.get("platform") or "Web").capitalize()
    url = job.get("url") or job.get("link") or ""
    salary = job.get("salary") or job.get("salary_stated") or "Belirtilmemiş"

    # Emoji badge based on score
    badge = "🔥 MÜKEMMEL EŞLEŞME" if score >= 90 else "⭐ YÜKSEK UYUM"

    msg = (
        f"<b>{badge} (%{score})</b>\n\n"
        f"💼 <b>Pozisyon:</b> {title}\n"
        f"🏢 <b>Şirket:</b> {company}\n"
        f"📍 <b>Lokasyon:</b> {location}\n"
        f"🌐 <b>Platform:</b> {platform}\n"
        f"💰 <b>Maaş:</b> {salary}\n\n"
    )
    if url:
        msg += f"👉 <a href='{url}'>İlana Git ve Başvur</a>\n"

    msg += "\n<i>Otonom İş Bulma Sistemi Radar Uyarısı</i>"

    sent = send_telegram_message(msg)
    if sent and job_id:
        conn = get_db_connection()
        try:
            conn.cursor().execute("INSERT OR IGNORE INTO telegram_alerted_jobs (job_id) VALUES (?)", (job_id,))
            conn.commit()
        finally:
            conn.close()
    return sent


def send_test_notification() -> Dict[str, Any]:
    """Send a test message to verify Telegram bot setup."""
    settings = get_telegram_settings()
    if not settings.get("bot_token") or not settings.get("chat_id"):
        return {"success": False, "error": "Bot Token veya Chat ID eksik."}

    test_msg = (
        "🤖 <b>Otonom İş Bulma Sistemi — Bağlantı Başarılı!</b>\n\n"
        "Tebrikler! Telegram bildirim botunuz başarıyla bağlandı.\n"
        "Artık profilinize %75 ve üzeri uyan tüm yeni iş ilanları anında buraya gönderilecek.\n\n"
        "⚡ <i>İlk 60 dakika içinde başvurarak mülakat şansınızı 3 katına çıkarın!</i>"
    )
    success = send_telegram_message(test_msg)
    if success:
        return {"success": True, "message": "Test mesajı başarıyla Telegram'a gönderildi!"}
    else:
        return {"success": False, "error": "Telegram mesajı gönderilemedi. Token ve Chat ID'yi kontrol edin."}
