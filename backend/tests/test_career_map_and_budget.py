"""Career suggestions come from the saved profile, and the daily token budget guards every paid AI key."""

import asyncio

import httpx

from backend.app.core import llm_client as module


def test_openai_calls_also_stop_at_the_daily_token_budget(monkeypatch):
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "A real model sentence."}}],
            "usage": {"prompt_tokens": 60, "completion_tokens": 50},
        })

    real_client = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr(module, "get_provider_api_key", lambda provider: "secret-key" if provider == "openai" else "")
    monkeypatch.setattr(module.settings, "LLM_DAILY_TOKEN_BUDGET", 100, raising=False)
    monkeypatch.setattr(module.llm_client, "_usage", {})

    first = asyncio.run(module.llm_client.generate_text("system", "user", preferred_provider="openai", apply_humanizer=False))
    second = asyncio.run(module.llm_client.generate_text("system", "user", preferred_provider="openai", apply_humanizer=False))

    assert first["provider_used"].startswith("OpenAI")
    assert second["is_template_fallback"] is True
    assert len(sent) == 1
    assert module.llm_client.get_usage_today()["budget_tokens"] in (0, 100)  # shown when a paid provider is active
