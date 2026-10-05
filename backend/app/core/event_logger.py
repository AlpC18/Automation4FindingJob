"""
Realtime Agent Event Logger & Live Terminal Streamer
Captures agent thoughts, actions, scraping steps, and Anti-AI sanitization passes,
broadcasting them to the frontend via Server-Sent Events (SSE) or REST history.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any

class AgentEventLogger:
    def __init__(self, max_history: int = 200):
        self.max_history = max_history
        self.logs: List[Dict[str, Any]] = []

    def log_event(self, module: str, message: str, level: str = "INFO"):
        normalized_level = level.upper()
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "module": module.upper(),
            "level": normalized_level,
            "message": message
        }
        self.logs.append(entry)
        logger = logging.getLogger("career_agent")
        logger.log(getattr(logging, normalized_level, logging.INFO), f"[{module.upper()}] {message}", extra={"agent_module": module.upper()})
        if len(self.logs) > self.max_history:
            self.logs.pop(0)

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.logs[-limit:]

agent_logger = AgentEventLogger()
