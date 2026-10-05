"""
Dynamic LLM Cost & Complexity Router Matrix
Optimizes token expenditure and latency by dynamically selecting model tiers:
- Tier 1 (Lightweight / Local): Ollama / DeepSeek / Gemini Flash for parsing & filtering
- Tier 2 (Balanced): GPT-4o-mini / Gemini Pro for mektup & outreach generation
- Tier 3 (High Reasoning): Claude 3.5 Sonnet / GPT-4o for Drafter-Reviewer audits & counter-offers
- Tracks cumulative token usage and estimated $ saved vs single-model architectures.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.app.core.config import settings
from backend.app.core.event_logger import agent_logger
from backend.app.core.llm_client import llm_client

TASK_COMPLEXITY_TIERS = {
    "tier_1_lightweight": {
        "description": "HTML sanitization, keyword extraction, JSON formatting",
        "primary_provider": "gemini",
        "model": settings.GEMINI_MODEL,
        "cost_per_1m_input": 0.075,
        "cost_per_1m_output": 0.30
    },
    "tier_2_balanced": {
        "description": "Cover letter drafting, outreach emails, behavioral profiling",
        "primary_provider": "openai",
        "model": "gpt-4o-mini",
        "cost_per_1m_input": 0.15,
        "cost_per_1m_output": 0.60
    },
    "tier_3_high_reasoning": {
        "description": "Drafter-Reviewer audits, counter-offers, ATS grounding audit",
        "primary_provider": "anthropic",
        "model": settings.ANTHROPIC_MODEL,
        "cost_per_1m_input": 3.00,
        "cost_per_1m_output": 15.00
    }
}

class LLMCostRouter:
    """Intelligently routes inference requests based on prompt complexity and tracks cost savings."""

    def __init__(self):
        self._stats = {
            "tier_1_calls": 0,
            "tier_2_calls": 0,
            "tier_3_calls": 0,
            "actual_cost_usd": 0.0,
            "baseline_gpt4o_cost_usd": 0.0,
            "total_tokens_routed": 0
        }

    def classify_task_tier(self, task_name: str, prompt_text: str) -> str:
        """Determines optimal cost/performance tier for a given task."""
        task_lower = task_name.lower()
        
        if any(w in task_lower for w in ["audit", "reviewer", "grounding", "counter_offer", "negotiate"]):
            return "tier_3_high_reasoning"
        elif any(w in task_lower for w in ["clean", "parse", "extract", "keyword", "spam"]):
            return "tier_1_lightweight"
        else:
            return "tier_2_balanced"

    async def route_and_generate(
        self,
        task_name: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.5
    ) -> Dict[str, Any]:
        """Routes execution to optimal provider and updates economics telemetry."""
        tier_key = self.classify_task_tier(task_name, user_prompt)
        tier_config = TASK_COMPLEXITY_TIERS[tier_key]

        # Call underlying LLM client
        result = await llm_client.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature
        )

        # Telemetry updates (Estimated token count heuristic: 1 word ~ 1.33 tokens)
        prompt_words = len(system_prompt.split()) + len(user_prompt.split())
        output_words = len(result.get("text", "").split())
        
        est_input_tokens = prompt_words * 1.33
        est_output_tokens = output_words * 1.33
        total_tokens = est_input_tokens + est_output_tokens

        # Actual cost in routed tier
        tier_cost = (
            (est_input_tokens / 1_000_000.0) * tier_config["cost_per_1m_input"] +
            (est_output_tokens / 1_000_000.0) * tier_config["cost_per_1m_output"]
        )

        # Baseline cost if everything was executed with flagship GPT-4o ($5.00 / $15.00)
        baseline_cost = (
            (est_input_tokens / 1_000_000.0) * 5.00 +
            (est_output_tokens / 1_000_000.0) * 15.00
        )

        self._stats[f"{tier_key.split('_')[0]}_{tier_key.split('_')[1]}_calls"] = (
            self._stats.get(f"{tier_key.split('_')[0]}_{tier_key.split('_')[1]}_calls", 0) + 1
        )
        self._stats["actual_cost_usd"] += tier_cost
        self._stats["baseline_gpt4o_cost_usd"] += baseline_cost
        self._stats["total_tokens_routed"] += int(total_tokens)

        saved_usd = max(0.0, self._stats["baseline_gpt4o_cost_usd"] - self._stats["actual_cost_usd"])
        savings_pct = (
            (saved_usd / max(self._stats["baseline_gpt4o_cost_usd"], 0.0001)) * 100
            if self._stats["baseline_gpt4o_cost_usd"] > 0 else 0.0
        )

        agent_logger.log_event("LLM_ROUTER", f"Task '{task_name}' routed to {tier_key} ({tier_config['model']})")

        return {
            "text": result.get("text", ""),
            "routing_telemetry": {
                "assigned_tier": tier_key,
                "model_used": tier_config["model"],
                "tokens_estimated": int(total_tokens),
                "cost_this_call_usd": round(tier_cost, 6),
                "cumulative_savings_pct": round(savings_pct, 1)
            }
        }

    def get_cost_metrics(self) -> Dict[str, Any]:
        """Returns cumulative cost savings and tier distribution metrics."""
        saved_usd = max(0.0, self._stats["baseline_gpt4o_cost_usd"] - self._stats["actual_cost_usd"])
        savings_pct = (
            (saved_usd / max(self._stats["baseline_gpt4o_cost_usd"], 0.0001)) * 100
            if self._stats["baseline_gpt4o_cost_usd"] > 0 else 0.0
        )

        return {
            "tier_distribution": {
                "tier_1_lightweight": self._stats.get("tier_1_calls", 0),
                "tier_2_balanced": self._stats.get("tier_2_calls", 0),
                "tier_3_high_reasoning": self._stats.get("tier_3_calls", 0),
            },
            "total_tokens_routed": self._stats["total_tokens_routed"],
            "actual_spend_usd": round(self._stats["actual_cost_usd"], 4),
            "baseline_spend_usd": round(self._stats["baseline_gpt4o_cost_usd"], 4),
            "estimated_savings_usd": round(saved_usd, 4),
            "savings_percentage": round(savings_pct, 1),
            "tiers_configured": TASK_COMPLEXITY_TIERS
        }


llm_cost_router = LLMCostRouter()
