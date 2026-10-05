"""Which product features work right now, and what is missing for the ones that do not."""

from typing import Any, Dict, List

from backend.app.core.config import settings


def _capability(identifier: str, level: str, href: str, **extra: Any) -> Dict[str, Any]:
    return {"id": identifier, "level": level, "href": href, **extra}


def build_capabilities(
    *,
    llm_provider: str,
    scraper_enabled: bool,
    ready_portals: List[str],
    smtp_ready: bool,
    inbox_connected: bool,
    apollo_ready: bool,
    proxy_ready: bool,
    daemon_running: bool,
) -> Dict[str, Any]:
    """Level is "on", "limited" (works through a weaker fallback) or "off"."""
    capabilities = [
        _capability("ai_writing", "limited" if llm_provider == "local_fallback" else "on", "/llm", provider=llm_provider),
        _capability(
            "job_scan",
            "off" if not scraper_enabled else ("on" if ready_portals else "limited"),
            "/sources",
            portals=ready_portals,
        ),
        _capability("email_send", "on" if smtp_ready else "off", "/preferences"),
        _capability("inbox_sync", "on" if inbox_connected else "off", "/inbox"),
        _capability("decision_makers", "on" if apollo_ready else "limited", "/decision-makers"),
        _capability("stealth_proxy", "on" if proxy_ready else "limited", "/safety"),
        _capability("automation", "on" if daemon_running else "off", "/daemon-settings"),
    ]
    return {
        "capabilities": capabilities,
        "summary": {level: sum(1 for item in capabilities if item["level"] == level) for level in ("on", "limited", "off")},
    }


async def get_capabilities(verify: bool = False) -> Dict[str, Any]:
    """Feature readiness. With ``verify`` the AI provider is called once for real, because a
    saved key says nothing about whether the provider actually answers (billing, retired model)."""
    from backend.app.core.llm_client import llm_client
    from backend.app.core.smtp_credentials import smtp_configuration_status
    from backend.app.modules.outcome.oauth_mail_agent import oauth_mail_agent
    from backend.app.modules.scrape.source_registry import ACTOR_SOURCES, get_source_health
    from backend.app.tasks.scheduler_daemon import scheduler_daemon

    source_health = get_source_health()
    provider = llm_client.get_effective_provider()
    result = build_capabilities(
        llm_provider=provider,
        scraper_enabled=settings.SCRAPER_MODE.lower() != "disabled",
        ready_portals=[source for source in ACTOR_SOURCES if source_health.get(source, {}).get("configured")],
        smtp_ready=bool(smtp_configuration_status()["configured"]),
        inbox_connected=any(account["connected"] for account in oauth_mail_agent.get_accounts_status().values()),
        apollo_ready=bool(settings.APOLLO_API_KEY),
        proxy_ready=bool(settings.RESIDENTIAL_PROXY_URL),
        daemon_running=bool(scheduler_daemon.get_status()["is_running"]),
    )
    if verify and provider != "local_fallback":
        check = await llm_client.test_provider_connection(provider)
        if check.get("status") != "SUCCESS":
            ai = next(item for item in result["capabilities"] if item["id"] == "ai_writing")
            ai.update(level="off", error=str(check.get("message") or "")[:300])
            levels = [item["level"] for item in result["capabilities"]]
            result["summary"] = {level: levels.count(level) for level in ("on", "limited", "off")}
    return result
