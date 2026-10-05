"""
Account Health & Rate Limiter Engine
Protects user accounts against shadowbans and platform restrictions by enforcing
autonomous daily quotas, randomized human jitter delays, and activity auditing.
"""

import time
import random
from datetime import datetime, date
from typing import Dict, Any, Tuple
from backend.app.core.config import settings
from backend.app.core.database import get_db_connection

class AccountHealthManager:
    def __init__(self):
        self.limits = {
            "linkedin": settings.DAILY_LIMIT_LINKEDIN,
            "upwork": settings.DAILY_LIMIT_UPWORK,
            "kosovajob": settings.DAILY_LIMIT_KOSOVAJOB,
            "remote": settings.DAILY_LIMIT_GLOBAL_REMOTE,
        }

    def get_today_usage(self, platform: str) -> int:
        conn = get_db_connection()
        cursor = conn.cursor()
        today_str = date.today().isoformat()
        cursor.execute("""
            SELECT COUNT(*) as count FROM account_activity_log
            WHERE platform = ? AND DATE(timestamp) = ? AND action_type IN ('apply', 'message')
        """, (platform.lower(), today_str))
        row = cursor.fetchone()
        count = row["count"] if row else 0
        conn.close()
        return count

    def can_perform_action(self, platform: str, action_type: str = "apply") -> Tuple[bool, str, Dict[str, Any]]:
        platform_key = platform.lower()
        limit = self.limits.get(platform_key, 25)
        usage = self.get_today_usage(platform_key)
        
        remaining = max(0, limit - usage)
        health_percentage = round((remaining / limit) * 100, 1)
        
        status_label = "HEALTHY"
        if remaining == 0:
            status_label = "QUOTA_EXHAUSTED"
            return False, f"Daily safety quota reached for {platform.capitalize()} ({usage}/{limit}). Actions paused to avoid shadowban.", {
                "platform": platform,
                "usage": usage,
                "limit": limit,
                "remaining": remaining,
                "health_percentage": 0.0,
                "status": status_label
            }
        elif remaining < 5:
            status_label = "WARNING"
            
        metrics = {
            "platform": platform,
            "usage": usage,
            "limit": limit,
            "remaining": remaining,
            "health_percentage": health_percentage,
            "status": status_label
        }
        return True, "Action allowed within safety boundaries.", metrics

    def log_action(self, platform: str, action_type: str, status: str = "SUCCESS", target_info: str = ""):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO account_activity_log (platform, action_type, status, target_info)
            VALUES (?, ?, ?, ?)
        """, (platform.lower(), action_type, status, target_info))
        conn.commit()
        conn.close()

    def get_all_platform_health(self) -> Dict[str, Any]:
        results = {}
        for plat, limit in self.limits.items():
            usage = self.get_today_usage(plat)
            remaining = max(0, limit - usage)
            results[plat] = {
                "platform": plat.capitalize(),
                "daily_limit": limit,
                "used_today": usage,
                "remaining": remaining,
                "health_pct": round((remaining / limit) * 100, 1),
                "is_safe": remaining > 0
            }
        return results

    def human_jitter_delay(self, min_seconds: float = 1.5, max_seconds: float = 4.0):
        """
        Simulates natural human hesitation to prevent robotic scraping/application spikes.
        """
        delay = round(random.uniform(min_seconds, max_seconds), 2)
        time.sleep(delay)
        return delay

account_health = AccountHealthManager()
