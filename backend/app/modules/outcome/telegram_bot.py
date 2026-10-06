"""
Telegram Mobile Command Center & Dispatch Bot
Enables 24/7 autonomous mobile monitoring, daily career briefings,
instant interview notifications, and inline approval commands.
"""

import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.app.core.config import settings
from backend.app.core.database import get_db_connection
from backend.app.core.event_logger import agent_logger
from backend.app.api.profile import fetch_candidate_profile

class TelegramBotManager:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.bot_token.strip() and self.chat_id and self.chat_id.strip())

    async def send_message(self, text: str, target_chat_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Dispatches message to Telegram official API or logs into simulated queue if no token configured.
        """
        chat_id = target_chat_id or self.chat_id
        if self.is_configured():
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True
                    })
                    data = resp.json()
                    status = "DELIVERED" if data.get("ok") else "FAILED"
                    self._record_event("OUTGOING_MESSAGE", text, chat_id, status)
                    return {"status": status, "telegram_response": data}
            except Exception as e:
                self._record_event("OUTGOING_MESSAGE", text, chat_id, f"ERROR: {str(e)[:30]}")
                return {"status": "ERROR", "message": str(e)}
        else:
            # No bot token: nothing leaves this machine, so the event must not read as delivered.
            self._record_event("SIMULATED_DISPATCH", text, chat_id or "local_demo_chat", "NOT_CONFIGURED")
            agent_logger.log_event("TELEGRAM_BOT", f"[Not sent, Telegram is not configured] {text[:70]}...")
            return {
                "status": "NOT_CONFIGURED",
                "message": "Token not provided; message recorded in local database queue.",
                "preview": text[:120]
            }

    async def send_notification(self, text: str) -> Dict[str, Any]:
        """Send to the configured chat. The daemon, auto-apply and weekly digest all call this name."""
        return await self.send_message(text)

    async def dispatch_daily_briefing(self) -> Dict[str, Any]:
        """
        Constructs and sends an intelligent daily summary of matching jobs, ghost jobs, and pending actions.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM scraped_jobs WHERE (stale_at IS NULL OR submission_confirmed = 1) AND match_score >= 80 ORDER BY match_score DESC LIMIT 4")
        top_jobs = cursor.fetchall()

        cursor.execute("SELECT count(*) as count FROM scraped_jobs WHERE ghost_score >= 35")
        ghost_count = cursor.fetchone()["count"]

        cursor.execute("SELECT count(*) as count FROM scraped_jobs WHERE status = 'Human Review'")
        review_count = cursor.fetchone()["count"]

        conn.close()
        candidate_profile = fetch_candidate_profile()
        cand_name = candidate_profile.get("full_name") or "Aday"

        briefing_text = f"🌅 *Otonom Kariyer Ajanı - Günlük Brifing*\n"
        briefing_text += f"📅 _{datetime.now().strftime('%d %B %Y - %H:%M')}_\n"
        briefing_text += f"👤 Aday: *{cand_name}*\n\n"

        briefing_text += f"📊 *Özet Durum:*\n"
        briefing_text += f"• 👻 Elenen Hayalet İlan: *{ghost_count} adet*\n"
        briefing_text += f"• 🔍 Onay Bekleyen Başvuru: *{review_count} adet*\n\n"

        briefing_text += f"🔥 *Günün En Yüksek ATS Eşleşmeleri:*\n"
        if top_jobs:
            for i, j in enumerate(top_jobs, 1):
                briefing_text += f"{i}. *{j['title']}* @ {j['company']}\n"
                briefing_text += f"   🎯 ATS: %{int(j['match_score'])} • 📍 {j['location']} ({j['platform'].upper()})\n"
                briefing_text += f"   💡 Komut: `/apply_{j['id'][:8]}`\n"
        else:
            briefing_text += "• Bugün için henüz yeni taranmış yüksek eşleşmeli ilan bulunmuyor.\n"

        briefing_text += f"\n📱 _Cevaplamak için komutları kullanın veya panoyu açın: {settings.FRONTEND_PUBLIC_URL}_"

        res = await self.send_message(briefing_text)
        return {"briefing": briefing_text, "dispatch_status": res}

    async def send_interview_alert(self, company: str, role: str, meet_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends high-priority push notification when an interview invite is detected in inbox.
        """
        msg = f"🎉 *TEBRİKLER! MÜLAKAT DAVETİ ALINDI!*\n\n"
        msg += f"🏢 Şirket: *{company}*\n"
        msg += f"💼 Rol: *{role}*\n"
        if meet_url:
            msg += f"🔗 Toplantı Linki: {meet_url}\n"
        msg += f"\n🎙️ Pratik yapmak için Sesli Mülakat Koçunu başlatabilirsiniz!"
        return await self.send_message(msg)

    def handle_incoming_command(self, command_text: str) -> Dict[str, Any]:
        """
        Interprets commands sent by user in Telegram (/status, /apply_<id>, /help).
        """
        cmd = command_text.strip().lower()
        if cmd == "/start" or cmd == "/help":
            reply = (
                "🤖 *Otonom Kariyer Ajanı Komutları:*\n"
                "• `/briefing` - Günlük ilan ve başvuru özetini getir\n"
                "• `/status` - Kanban takip aşamalarını listele\n"
                "• `/apply <job_id>` - İlana onay ver ve başvuruyu tamamla\n"
                "• `/safety` - Hesap güvenlik ve günlük limit durumunu gör"
            )
            return {"reply": reply, "action": "HELP"}

        elif cmd == "/status":
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT status, count(*) as count FROM scraped_jobs GROUP BY status")
            rows = cursor.fetchall()
            conn.close()
            lines = [f"• *{r['status']}:* {r['count']} ilan" for r in rows]
            reply = "📊 *Güncel Kanban Aşamaları:*\n" + "\n".join(lines)
            return {"reply": reply, "action": "STATUS"}

        elif cmd.startswith("/apply"):
            parts = cmd.split()
            job_id_prefix = parts[1] if len(parts) > 1 else ""
            reply = f"✅ `{job_id_prefix}` nolu ilan onaylandı! Playwright arka planda Easy Apply sürecini başlatıyor..."
            return {"reply": reply, "action": "APPROVE_APPLY", "target_id": job_id_prefix}

        return {"reply": "❓ Bilinmeyen komut. `/help` yazarak komut listesini görebilirsiniz.", "action": "UNKNOWN"}

    def get_recent_events(self, limit: int = 15) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM telegram_events ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def _record_event(self, event_type: str, text: str, chat_id: str, status: str):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO telegram_events (event_type, message_text, chat_id, status)
            VALUES (?, ?, ?, ?)
        """, (event_type, text, chat_id, status))
        conn.commit()
        conn.close()

telegram_bot = TelegramBotManager()
# Compatibility alias used by scheduler, digest and auto-apply modules.
telegram_dispatcher = telegram_bot
