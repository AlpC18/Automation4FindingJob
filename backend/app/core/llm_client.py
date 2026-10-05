"""
Multi-LLM Provider Engine (Factory Architecture)
Supports OpenAI, Anthropic Claude, Google Gemini, DeepSeek, and Local Ollama.
Falls back to high-grade deterministic templates when API keys are not supplied.
Automatically runs output through the Anti-AI Humanizer Engine.
"""

import json
import logging
import os
import re
import time
from datetime import date
import httpx
from typing import Dict, Any, List, Optional
from backend.app.core.config import settings
from backend.app.core.provider_credentials import get_provider_api_key
from backend.app.modules.apply.humanizer_engine import humanizer_engine

logger = logging.getLogger(__name__)


# Room for the model's own reasoning plus the longest reply the app asks for (a CV analysis with a full rewrite).
ANTHROPIC_MAX_TOKENS = 12000
ANTHROPIC_TIMEOUT_SECONDS = 240.0
# USD per million tokens (input, output), Anthropic list prices as of 2026-09; update when the price list changes.
ANTHROPIC_PRICES_USD_PER_MTOK = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}
TEMPLATE_ENGINE_LABELS = ("Fallback", "Deterministic Hybrid Engine")


class LLMBudgetExceeded(RuntimeError):
    """Today's paid-token budget is spent; the caller falls back to the template engine."""


def is_template_engine(provider_used: str) -> bool:
    """True when the text came from the built-in template engine instead of a language model."""
    return str(provider_used or "").startswith(TEMPLATE_ENGINE_LABELS)


def _describe_error(exc: Exception) -> str:
    """Status and provider message only: request URLs can carry API keys and must not be logged."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
    return type(exc).__name__

class LLMClient:
    def __init__(self):
        self.provider = settings.ACTIVE_LLM_PROVIDER.lower()
        self.custom_model: Optional[str] = None
        self.ollama_url = settings.OLLAMA_BASE_URL
        # ponytail: in-memory (day, input tokens, output tokens, calls) counter, resets on restart; persist it if restarts become a loophole.
        self._tokens_used = (None, 0, 0, 0)

    def _usage_today(self) -> tuple:
        day, tokens_in, tokens_out, calls = self._tokens_used
        return (tokens_in, tokens_out, calls) if day == date.today() else (0, 0, 0)

    def _tokens_used_today(self) -> int:
        tokens_in, tokens_out, _ = self._usage_today()
        return tokens_in + tokens_out

    def _record_tokens(self, tokens_in: int, tokens_out: int) -> None:
        used_in, used_out, calls = self._usage_today()
        self._tokens_used = (date.today(), used_in + tokens_in, used_out + tokens_out, calls + 1)

    def get_usage_today(self) -> Dict[str, Any]:
        """Today's Anthropic token use against the daily budget, with a list-price cost estimate."""
        tokens_in, tokens_out, calls = self._usage_today()
        model = self.custom_model if self.provider == "anthropic" and self.custom_model else settings.ANTHROPIC_MODEL
        prices = ANTHROPIC_PRICES_USD_PER_MTOK.get(model)
        # ponytail: prices every token at the current model; split per model if models get mixed within a day.
        cost = round((tokens_in * prices[0] + tokens_out * prices[1]) / 1_000_000, 4) if prices else None
        budget = max(0, settings.LLM_DAILY_TOKEN_BUDGET)
        used = tokens_in + tokens_out
        return {
            "provider": "anthropic",
            "model": model,
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "tokens_used": used,
            "budget_tokens": budget,
            "remaining_tokens": max(0, budget - used) if budget else None,
            "percent_used": round(min(100.0, used / budget * 100), 1) if budget else 0,
            "calls": calls,
            "estimated_cost_usd": cost,
            "average_cost_per_call_usd": round(cost / calls, 4) if cost is not None and calls else None,
        }

    def detect_available_provider(self) -> str:
        """Auto-detects the first properly configured active provider."""
        if get_provider_api_key("openai"):
            return "openai"
        if get_provider_api_key("gemini"):
            return "gemini"
        if get_provider_api_key("anthropic"):
            return "anthropic"
        if get_provider_api_key("deepseek"):
            return "deepseek"
        if self._custom_ready():
            return "custom"
        return "local_fallback"

    @staticmethod
    def _custom_ready() -> bool:
        return bool(settings.CUSTOM_LLM_BASE_URL.strip() and settings.CUSTOM_LLM_MODEL.strip() and get_provider_api_key("custom"))

    def get_effective_provider(self, requested_provider: Optional[str] = None) -> str:
        prov = (requested_provider or "auto").lower()
        if prov == "auto":
            # "auto" from the UI means "the configured default", not "first key found".
            prov = (self.provider or "auto").lower()
        if prov == "auto":
            return self.detect_available_provider()
        return prov

    def get_providers_status(self) -> Dict[str, Any]:
        """Returns the readiness status, configuration, and default models of all supported providers."""
        effective = self.get_effective_provider()
        return {
            "active_provider": self.provider,
            "effective_provider": effective,
            "providers": [
                {
                    "id": "openai",
                    "name": "OpenAI",
                    "model": self.custom_model if self.provider == "openai" and self.custom_model else settings.OPENAI_MODEL,
                    "available_models": ["gpt-4o", "gpt-4o-mini", "o1-preview", "gpt-4-turbo"],
                    "is_configured": bool(get_provider_api_key("openai")),
                    "type": "Cloud API"
                },
                {
                    "id": "gemini",
                    "name": "Google Gemini",
                    "model": self.custom_model if self.provider == "gemini" and self.custom_model else settings.GEMINI_MODEL,
                    "available_models": ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"],
                    "is_configured": bool(get_provider_api_key("gemini")),
                    "type": "Cloud API"
                },
                {
                    "id": "anthropic",
                    "name": "Anthropic Claude",
                    "model": self.custom_model if self.provider == "anthropic" and self.custom_model else settings.ANTHROPIC_MODEL,
                    "available_models": ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-4-5-20251001"],
                    "is_configured": bool(get_provider_api_key("anthropic")),
                    "type": "Cloud API"
                },
                {
                    "id": "deepseek",
                    "name": "DeepSeek",
                    "model": self.custom_model if self.provider == "deepseek" and self.custom_model else settings.DEEPSEEK_MODEL,
                    "available_models": ["deepseek-chat", "deepseek-coder"],
                    "is_configured": bool(get_provider_api_key("deepseek")),
                    "type": "Cloud API"
                },
                {
                    "id": "custom",
                    "name": "OpenAI-compatible (Groq, OpenRouter...)",
                    "model": self.custom_model if self.provider == "custom" and self.custom_model else settings.CUSTOM_LLM_MODEL,
                    "available_models": [settings.CUSTOM_LLM_MODEL] if settings.CUSTOM_LLM_MODEL else [],
                    "is_configured": self._custom_ready(),
                    "base_url": settings.CUSTOM_LLM_BASE_URL,
                    "type": "Cloud API"
                },
                {
                    "id": "ollama",
                    "name": "Local Ollama",
                    "model": self.custom_model if self.provider == "ollama" and self.custom_model else settings.OLLAMA_MODEL,
                    "available_models": ["llama3", "llama3.1", "mistral", "qwen2.5", "deepseek-r1"],
                    "is_configured": True,  # Accessible locally
                    "base_url": self.ollama_url,
                    "type": "Local Host"
                },
                {
                    "id": "local_fallback",
                    "name": "Deterministic Fallback Engine",
                    "model": "Smart Rule-Based NLP",
                    "available_models": ["Smart Rule-Based NLP"],
                    "is_configured": True,
                    "type": "Built-in Zero-Dependency"
                }
            ]
        }

    def set_active_provider(self, provider_id: str, model_name: Optional[str] = None):
        self.provider = provider_id.lower()
        # A model picked for the previous provider must not carry over to the new one.
        self.custom_model = model_name or None

    async def test_provider_connection(self, provider_id: str) -> Dict[str, Any]:
        """
        Sends a lightweight test ping to verify API key validity, connectivity, and latency.
        """
        start_time = time.time()
        prov = provider_id.lower()
        test_sys = "You are a connectivity test ping. Respond with only 'PONG'."
        test_user = "PING"

        try:
            if prov == "openai":
                if not get_provider_api_key("openai"):
                    return {"status": "ERROR", "message": "OpenAI API anahtarı bulunamadı.", "latency_ms": 0}
                await self._call_openai(test_sys, test_user, temp=0.0)
            elif prov == "gemini":
                if not get_provider_api_key("gemini"):
                    return {"status": "ERROR", "message": "Gemini API anahtarı bulunamadı.", "latency_ms": 0}
                await self._call_gemini(test_sys, test_user)
            elif prov == "anthropic":
                if not get_provider_api_key("anthropic"):
                    return {"status": "ERROR", "message": "Anthropic API anahtarı bulunamadı.", "latency_ms": 0}
                await self._call_anthropic(test_sys, test_user, temp=0.0)
            elif prov == "deepseek":
                if not get_provider_api_key("deepseek"):
                    return {"status": "ERROR", "message": "DeepSeek API anahtarı bulunamadı.", "latency_ms": 0}
                await self._call_deepseek(test_sys, test_user, temp=0.0)
            elif prov == "custom":
                if not self._custom_ready():
                    return {"status": "ERROR", "message": "CUSTOM_LLM_BASE_URL, CUSTOM_LLM_MODEL ve API anahtarı gerekli.", "latency_ms": 0}
                await self._call_custom(test_sys, test_user, temp=0.0)
            elif prov == "ollama":
                await self._call_ollama(test_sys, test_user)
            elif prov == "local_fallback":
                self._fallback_generation(test_sys, test_user)
            else:
                return {"status": "ERROR", "message": f"Bilinmeyen sağlayıcı: {provider_id}", "latency_ms": 0}

            latency = round((time.time() - start_time) * 1000, 1)
            return {
                "status": "SUCCESS",
                "provider": prov,
                "message": f"{prov.upper()} bağlantısı doğrulandı.",
                "latency_ms": latency
            }
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 1)
            return {
                "status": "ERROR",
                "provider": prov,
                "message": f"Sağlayıcı isteği başarısız oldu ({_describe_error(exc)}).",
                "latency_ms": latency
            }

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        preferred_provider: Optional[str] = None,
        temperature: float = 0.7,
        apply_humanizer: bool = True
    ) -> Dict[str, Any]:
        """
        Executes generation through the selected provider and verifies through Humanizer.
        """
        provider = self.get_effective_provider(preferred_provider)
        raw_output = ""
        provider_used = provider

        try:
            if provider == "openai" and get_provider_api_key("openai"):
                raw_output = await self._call_openai(system_prompt, user_prompt, temperature)
                provider_used = f"OpenAI ({self.custom_model or settings.OPENAI_MODEL})"
            elif provider == "gemini" and get_provider_api_key("gemini"):
                raw_output = await self._call_gemini(system_prompt, user_prompt)
                provider_used = f"Google Gemini ({self.custom_model or settings.GEMINI_MODEL})"
            elif provider == "anthropic" and get_provider_api_key("anthropic"):
                raw_output = await self._call_anthropic(system_prompt, user_prompt, temperature)
                provider_used = f"Anthropic ({self.custom_model or settings.ANTHROPIC_MODEL})"
            elif provider == "deepseek" and get_provider_api_key("deepseek"):
                raw_output = await self._call_deepseek(system_prompt, user_prompt, temperature)
                provider_used = f"DeepSeek ({self.custom_model or settings.DEEPSEEK_MODEL})"
            elif provider == "custom" and self._custom_ready():
                raw_output = await self._call_custom(system_prompt, user_prompt, temperature)
                provider_used = f"Custom ({self.custom_model if self.provider == 'custom' and self.custom_model else settings.CUSTOM_LLM_MODEL})"
            elif provider == "ollama":
                raw_output = await self._call_ollama(system_prompt, user_prompt)
                provider_used = f"Local Ollama ({self.custom_model or settings.OLLAMA_MODEL})"
            else:
                raw_output = self._fallback_generation(system_prompt, user_prompt)
                provider_used = "Deterministic Hybrid Engine"
        except Exception as exc:
            # Graceful fallback on network/rate-limit error. Logged because the fallback
            # text is a template: without this the provider failure is invisible.
            logger.warning("LLM provider %s failed (%s); using the template fallback engine.", provider, _describe_error(exc))
            raw_output = self._fallback_generation(system_prompt, user_prompt)
            provider_used = "Fallback Engine (API Error)"

        if not raw_output or not raw_output.strip():
            raw_output = self._fallback_generation(system_prompt, user_prompt)
            provider_used = "Fallback (Empty output rescued)"

        if apply_humanizer:
            # Run through Anti-AI Humanizer Engine
            clean_text, metrics = humanizer_engine.humanize_draft(raw_output, style_profile={})
            return {
                "text": clean_text,
                "raw_text": raw_output,
                "provider_used": provider_used,
                "human_texture_score": metrics.get("score", 90.0),
                "burstiness": metrics.get("burstiness", 0.65),
                "is_human_verified": metrics.get("is_human_verified", True),
                "metrics": metrics
            }
        else:
            return {
                "text": raw_output,
                "raw_text": raw_output,
                "provider_used": provider_used,
                "human_texture_score": 90.0,
                "burstiness": 0.65,
                "is_human_verified": True,
                "metrics": {}
            }

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        preferred_provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate and safely parse a structured response from any provider.

        Providers are asked for JSON by their callers, but responses can still
        arrive wrapped in Markdown fences or with a short explanatory prefix.
        Returning an empty mapping lets domain agents use their deterministic
        fallback instead of failing with an AttributeError.
        """
        result = await self.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            preferred_provider=preferred_provider,
            temperature=0.2,
            apply_humanizer=False,
        )
        return self.extract_json(result.get("text") or "")

    @staticmethod
    def extract_json(text: str) -> Dict[str, Any]:
        """Parse a JSON object out of model text that may be fenced or prefixed; {} when there is none."""
        raw = (text or "").strip()
        candidates = [raw]
        fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            candidates.insert(0, fenced.group(1).strip())
        object_match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if object_match:
            candidates.append(object_match.group(0))

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(parsed, dict):
                return parsed
        return {}

    async def _call_openai(self, system_prompt: str, user_prompt: str, temp: float) -> str:
        model = self.custom_model if self.provider == "openai" and self.custom_model else settings.OPENAI_MODEL
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {get_provider_api_key('openai')}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": temp
                }
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _call_deepseek(self, system_prompt: str, user_prompt: str, temp: float) -> str:
        model = self.custom_model if self.provider == "deepseek" and self.custom_model else settings.DEEPSEEK_MODEL
        async with httpx.AsyncClient(timeout=35.0) as client:
            resp = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {get_provider_api_key('deepseek')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": temp
                }
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _call_custom(self, system_prompt: str, user_prompt: str, temp: float) -> str:
        """Chat completion against any OpenAI-compatible endpoint (CUSTOM_LLM_BASE_URL)."""
        model = self.custom_model if self.provider == "custom" and self.custom_model else settings.CUSTOM_LLM_MODEL
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.CUSTOM_LLM_BASE_URL.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {get_provider_api_key('custom')}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": temp
                }
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def _call_anthropic(self, system_prompt: str, user_prompt: str, temp: float) -> str:
        budget = settings.LLM_DAILY_TOKEN_BUDGET
        if budget > 0 and self._tokens_used_today() >= budget:
            raise LLMBudgetExceeded(f"daily token budget of {budget} is spent")
        model = self.custom_model if self.provider == "anthropic" and self.custom_model else settings.ANTHROPIC_MODEL
        async with httpx.AsyncClient(timeout=ANTHROPIC_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": get_provider_api_key("anthropic"),
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": model,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                    # No "temperature": current Claude models reject it with HTTP 400.
                    "max_tokens": ANTHROPIC_MAX_TOKENS,
                }
            )
            resp.raise_for_status()
            # The reply is a list of blocks and the first one is not always text
            # (current models may emit a thinking block first), so keep every text block.
            data = resp.json()
            usage = data.get("usage") or {}
            self._record_tokens(int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0))
            if data.get("stop_reason") == "max_tokens":
                # A cut-off reply usually means broken JSON downstream; make the cause visible.
                logger.warning("Anthropic reply was cut off at max_tokens=%s.", ANTHROPIC_MAX_TOKENS)
            blocks = data.get("content") or []
            return "".join(block.get("text", "") for block in blocks if isinstance(block, dict) and block.get("type") == "text")

    async def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        model = self.custom_model if self.provider == "gemini" and self.custom_model else settings.GEMINI_MODEL
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={get_provider_api_key('gemini')}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                json={
                    "contents": [{
                        "parts": [{"text": f"System Directive:\n{system_prompt}\n\nTask:\n{user_prompt}"}]
                    }]
                }
            )
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    async def _call_ollama(self, system_prompt: str, user_prompt: str) -> str:
        model = self.custom_model if self.provider == "ollama" and self.custom_model else settings.OLLAMA_MODEL
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model,
                    "system": system_prompt,
                    "prompt": user_prompt,
                    "stream": False
                }
            )
            resp.raise_for_status()
            return resp.json().get("response", "")

    def _fallback_generation(self, system_prompt: str, user_prompt: str) -> str:
        """
        High-grade rule-based generation adhering strictly to the Anti-AI Humanizer criteria.
        """
        return f"""Hi there,

I am writing regarding the open position. Having engineered scalable distributed systems and resilient microservices, I focus on clean technical execution and reliable software delivery.

In my recent projects, I developed real-time architectures that directly reduced operational overhead and improved system reliability. My engineering style favors maintainable code, test-driven reliability, and pragmatic problem solving over unnecessary complexity.

I would be glad to discuss how my hands-on background aligns with your current technical goals.

Best regards,
Candidate"""

llm_client = LLMClient()
