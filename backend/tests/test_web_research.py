from backend.app.modules.scrape import web_research

PAGE = "<html><script>x()</script><style>p{}</style><body>" + "<p>Real job text &amp; details.</p>" * 20 + "</body></html>"


def _public(monkeypatch):
    private = ("127.", "10.", "169.254.", "localhost")
    monkeypatch.setattr(
        "backend.app.modules.scrape.job_link_health._public_http_url",
        lambda url: (not any(part in url for part in private), "private"),
    )


def test_redirect_to_a_private_address_is_not_followed(monkeypatch):
    _public(monkeypatch)
    fetched = []

    def once(url, user_agent, timeout):
        fetched.append(url)
        return "", 302, "http://169.254.169.254/latest/meta-data/"

    monkeypatch.setattr(web_research, "_curl_once", once)
    body, code = web_research._curl_fetch("https://example.com/job", web_research.BOT_UA)
    assert (body, code) == ("", 0)
    assert fetched == ["https://example.com/job"]


def test_public_redirects_are_followed_up_to_the_limit(monkeypatch):
    _public(monkeypatch)
    hops = {"https://a.example/": ("", 301, "https://b.example/"), "https://b.example/": (PAGE, 200, "")}
    monkeypatch.setattr(web_research, "_curl_once", lambda url, ua, timeout: hops[url])
    assert web_research._curl_fetch("https://a.example/", web_research.BOT_UA) == (PAGE, 200)

    monkeypatch.setattr(web_research, "_curl_once", lambda url, ua, timeout: ("", 302, url))
    assert web_research._curl_fetch("https://a.example/", web_research.BOT_UA) == ("", 0)


def test_direct_fetch_returns_text_without_scripts_or_tags(monkeypatch):
    _public(monkeypatch)
    monkeypatch.setattr(web_research, "_curl_fetch", lambda *a, **k: (PAGE, 200))
    result = web_research.web_research_engine.fetch_with_escalation("https://example.com/job")
    assert result["success"] and result["method"] == "direct_fetch"
    assert "Real job text & details." in result["content"]
    assert "x()" not in result["content"] and "<p>" not in result["content"]


def test_403_retries_with_browser_agent_only_when_robots_allows(monkeypatch):
    _public(monkeypatch)
    agents = []

    def fetch(url, user_agent, timeout=15):
        agents.append(user_agent)
        return (PAGE, 200) if user_agent == web_research.BROWSER_UA and "example.com" in url else ("", 403)

    monkeypatch.setattr(web_research, "_curl_fetch", fetch)
    monkeypatch.setattr(web_research, "check_robots_permission", lambda url: (True, ""))
    result = web_research.web_research_engine.fetch_with_escalation("https://example.com/job")
    assert result["method"] == "browser_ua_retry"

    agents.clear()
    monkeypatch.setattr(web_research, "check_robots_permission", lambda url: (False, "disallowed"))
    monkeypatch.setattr(web_research.WebResearchEngine, "_try_google_cache", lambda self, url: None)
    monkeypatch.setattr(web_research.WebResearchEngine, "_try_wayback", lambda self, url: None)
    result = web_research.web_research_engine.fetch_with_escalation("https://example.com/job")
    assert not result["success"] and result["method"] == "all_failed"
    assert agents == [web_research.BOT_UA]
