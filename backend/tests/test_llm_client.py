"""Provider calls must match the live API, and a failing provider must not fail silently."""

import asyncio
import logging

import httpx

from backend.app.core import llm_client as module


def _client_returning(monkeypatch, status, body, sent):
    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(status, json=body)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr(module, "get_provider_api_key", lambda provider: "secret-key" if provider == "anthropic" else "")


def test_anthropic_request_omits_temperature_and_returns_model_text(monkeypatch):
    sent = []
    _client_returning(monkeypatch, 200, {"content": [{"type": "text", "text": "A real model sentence."}]}, sent)

    result = asyncio.run(module.llm_client.generate_text("system", "user", preferred_provider="anthropic", apply_humanizer=False))

    payload = __import__("json").loads(sent[0].content)
    assert "temperature" not in payload
    assert payload["model"] == module.settings.ANTHROPIC_MODEL
    assert sent[0].headers["x-api-key"] == "secret-key"
    assert result["provider_used"].startswith("Anthropic")


def test_provider_failure_is_logged_without_leaking_the_key(monkeypatch, caplog):
    sent = []
    _client_returning(monkeypatch, 400, {"error": {"message": "`temperature` is deprecated for this model."}}, sent)

    with caplog.at_level(logging.WARNING, logger=module.__name__):
        result = asyncio.run(module.llm_client.generate_text("system", "user", preferred_provider="anthropic", apply_humanizer=False))

    assert result["provider_used"] == "Fallback Engine (API Error)"
    assert "HTTP 400" in caplog.text and "anthropic" in caplog.text
    assert "secret-key" not in caplog.text


def test_anthropic_reply_with_a_leading_non_text_block_still_yields_the_text(monkeypatch):
    sent = []
    body = {"content": [{"type": "thinking", "thinking": "plan"}, {"type": "text", "text": "Dear team, "}, {"type": "text", "text": "hello."}]}
    _client_returning(monkeypatch, 200, body, sent)

    result = asyncio.run(module.llm_client.generate_text("system", "user", preferred_provider="anthropic", apply_humanizer=False))

    assert result["text"] == "Dear team, hello."
    assert result["provider_used"].startswith("Anthropic")


def test_anthropic_calls_stop_once_the_daily_token_budget_is_spent(monkeypatch, caplog):
    sent = []
    body = {"content": [{"type": "text", "text": "A real model sentence."}], "usage": {"input_tokens": 60, "output_tokens": 50}}
    _client_returning(monkeypatch, 200, body, sent)
    monkeypatch.setattr(module.settings, "LLM_DAILY_TOKEN_BUDGET", 100, raising=False)
    monkeypatch.setattr(module.llm_client, "_tokens_used", (None, 0, 0, 0), raising=False)

    first = asyncio.run(module.llm_client.generate_text("system", "user", preferred_provider="anthropic", apply_humanizer=False))
    with caplog.at_level(logging.WARNING, logger=module.__name__):
        second = asyncio.run(module.llm_client.generate_text("system", "user", preferred_provider="anthropic", apply_humanizer=False))

    assert first["provider_used"].startswith("Anthropic")
    assert second["provider_used"] == "Fallback Engine (API Error)"
    assert len(sent) == 1
    assert "LLMBudgetExceeded" in caplog.text


def test_custom_openai_compatible_provider_calls_the_configured_endpoint(monkeypatch):
    sent = []
    _client_returning(monkeypatch, 200, {"choices": [{"message": {"content": "A free model sentence."}}]}, sent)
    monkeypatch.setattr(module, "get_provider_api_key", lambda provider: "free-key" if provider == "custom" else "")
    monkeypatch.setattr(module.settings, "CUSTOM_LLM_BASE_URL", "https://api.example.test/openai/v1/")
    monkeypatch.setattr(module.settings, "CUSTOM_LLM_MODEL", "some-free-model")

    result = asyncio.run(module.llm_client.generate_text("system", "user", preferred_provider="custom", apply_humanizer=False))

    assert str(sent[0].url) == "https://api.example.test/openai/v1/chat/completions"
    assert sent[0].headers["authorization"] == "Bearer free-key"
    assert result["text"] == "A free model sentence."
    assert result["provider_used"] == "Custom (some-free-model)"


def test_usage_report_counts_tokens_and_estimates_cost_at_list_price(monkeypatch):
    sent = []
    body = {"content": [{"type": "text", "text": "A real model sentence."}], "usage": {"input_tokens": 1000, "output_tokens": 500}}
    _client_returning(monkeypatch, 200, body, sent)
    monkeypatch.setattr(module.settings, "LLM_DAILY_TOKEN_BUDGET", 6000)
    monkeypatch.setattr(module.settings, "ANTHROPIC_MODEL", "claude-sonnet-5-5")
    monkeypatch.setattr(module.llm_client, "provider", "anthropic")
    monkeypatch.setattr(module.llm_client, "custom_model", None)
    monkeypatch.setattr(module.llm_client, "_tokens_used", (None, 0, 0, 0))

    for _ in range(2):
        asyncio.run(module.llm_client.generate_text("system", "user", preferred_provider="anthropic", apply_humanizer=False))
    usage = module.llm_client.get_usage_today()

    assert (usage["input_tokens"], usage["output_tokens"], usage["calls"]) == (2000, 1000, 2)
    assert (usage["tokens_used"], usage["remaining_tokens"], usage["percent_used"]) == (3000, 3000, 50.0)
    # 2000 input at $2/M + 1000 output at $10/M
    assert usage["estimated_cost_usd"] == 0.014
    assert usage["average_cost_per_call_usd"] == 0.007


def test_switching_provider_drops_the_model_chosen_for_the_previous_one(monkeypatch):
    monkeypatch.setattr(module.llm_client, "provider", "deepseek")
    monkeypatch.setattr(module.llm_client, "custom_model", "deepseek-coder")
    module.llm_client.set_active_provider("anthropic")
    assert (module.llm_client.provider, module.llm_client.custom_model) == ("anthropic", None)
    module.llm_client.set_active_provider("anthropic", "claude-haiku-4-5")
    assert module.llm_client.custom_model == "claude-haiku-4-5"
