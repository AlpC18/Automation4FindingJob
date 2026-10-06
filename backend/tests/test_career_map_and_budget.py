"""Career suggestions come from the saved profile, and the daily token budget guards every paid AI key."""

import asyncio

import httpx

from backend.app.core import llm_client as module
from backend.app.modules.setup.career_discovery import career_discovery_engine


def test_a_frontend_profile_gets_no_ai_or_backend_suggestions():
    result = career_discovery_engine.discover_latent_opportunities({"target_role": "Frontend Developer", "skills": ["React", "TypeScript"]})

    titles = [track["title"] for track in result["lateral_pivots"] + result["emerging_frontiers"]]
    assert result["detected_competency_domains"] == ["fullstack"]
    assert result["emerging_frontiers"] == []
    assert not any("AI" in title or "Backend" in title for title in titles)
    assert all("React" in track["match_reason"] for track in result["lateral_pivots"])
    assert all("Frontend Developer" in query or query in titles for query in result["recommended_search_queries"])


def test_an_ai_profile_gets_an_ai_frontier_grounded_in_its_own_skills():
    result = career_discovery_engine.discover_latent_opportunities({"target_role": "ML Engineer", "skills": ["PyTorch", "RAG"], "years_of_experience": 2})

    assert len(result["emerging_frontiers"]) == 1
    assert "PyTorch" in result["emerging_frontiers"][0]["match_reason"]
    assert "2" in result["core_progression"][0]["match_reason"]


def test_an_empty_profile_gets_no_invented_experience():
    result = career_discovery_engine.discover_latent_opportunities({})

    assert result["lateral_pivots"] == [] and result["emerging_frontiers"] == []
    assert "yıl" not in result["core_progression"][0]["match_reason"]


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
