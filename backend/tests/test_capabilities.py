"""Feature readiness shown on the system status screen."""

from fastapi.testclient import TestClient

from backend.app.core.capabilities import build_capabilities
from backend.app.main import app

NOTHING = {
    "llm_provider": "local_fallback", "scraper_enabled": True, "ready_portals": [], "smtp_ready": False,
    "inbox_connected": False, "proxy_ready": False, "daemon_running": False,
}


def _levels(**overrides):
    result = build_capabilities(**{**NOTHING, **overrides})
    return {item["id"]: item["level"] for item in result["capabilities"]}, result


def test_fresh_install_separates_fallbacks_from_features_that_are_off():
    levels, result = _levels()
    assert levels == {
        "ai_writing": "limited", "job_scan": "limited", "email_send": "off", "inbox_sync": "off",
        "stealth_proxy": "limited", "automation": "off",
    }
    assert result["summary"] == {"on": 0, "limited": 3, "off": 3}
    assert all(item["href"].startswith("/") for item in result["capabilities"])


def test_configuring_a_dependency_turns_its_feature_on():
    levels, result = _levels(
        llm_provider="gemini", ready_portals=["linkedin"], smtp_ready=True, inbox_connected=True, proxy_ready=True,
        daemon_running=True,
    )
    assert set(levels.values()) == {"on"}
    assert result["summary"] == {"on": 6, "limited": 0, "off": 0}


def test_disabled_scraper_is_off_even_with_configured_portals():
    levels, _ = _levels(scraper_enabled=False, ready_portals=["linkedin"])
    assert levels["job_scan"] == "off"


def test_capabilities_endpoint_serves_every_feature():
    response = TestClient(app).get("/api/system/capabilities")
    assert response.status_code == 200
    assert len(response.json()["capabilities"]) == 6


def test_verify_marks_ai_off_when_the_configured_provider_does_not_answer(monkeypatch):
    from backend.app.core import llm_client as llm_module

    async def failing(provider):
        return {"status": "ERROR", "message": "Sağlayıcı isteği başarısız oldu (HTTP 400: free tier not available)."}

    async def working(provider):
        return {"status": "SUCCESS"}

    monkeypatch.setattr(llm_module.llm_client, "provider", "gemini")
    monkeypatch.setattr(llm_module.llm_client, "test_provider_connection", failing)
    client = TestClient(app)

    unverified = client.get("/api/system/capabilities").json()["capabilities"][0]
    assert unverified["id"] == "ai_writing" and unverified["level"] == "on"

    verified = client.get("/api/system/capabilities?verify=true").json()
    assert verified["capabilities"][0]["level"] == "off"
    assert "free tier not available" in verified["capabilities"][0]["error"]
    assert verified["summary"]["off"] >= 1

    monkeypatch.setattr(llm_module.llm_client, "test_provider_connection", working)
    assert client.get("/api/system/capabilities?verify=true").json()["capabilities"][0]["level"] == "on"
