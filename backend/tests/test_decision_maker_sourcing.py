"""Spec 1.2 / 1.4: Apollo decision-maker search and the residential proxy for browser automation."""

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.modules.apply import decision_maker as dm
from backend.app.modules.scrape.stealth_browser import proxy_settings


def _apollo(monkeypatch, status=200, body=None, key="apollo-key"):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(status, json=body if body is not None else {"people": []}, request=httpx.Request("POST", url))

    monkeypatch.setattr(dm.settings, "APOLLO_API_KEY", key)
    monkeypatch.setattr(dm.httpx, "post", fake_post)
    return calls


@pytest.mark.parametrize("raw, expected", [
    ("acme.com", "acme.com"),
    ("https://www.Acme.com/careers", "acme.com"),
    ("jobs@sub.acme.co.uk", "sub.acme.co.uk"),
])
def test_company_domain_is_normalized(raw, expected):
    assert dm.normalize_company_domain(raw) == expected


@pytest.mark.parametrize("raw", ["", "acme", "acme .com", "http://", "a.b", "-acme.com"])
def test_invalid_company_domain_is_rejected(raw):
    with pytest.raises(ValueError):
        dm.normalize_company_domain(raw)


def test_apollo_search_sends_documented_request_and_maps_people(monkeypatch):
    calls = _apollo(monkeypatch, body={"people": [
        {"first_name": "Ada", "last_name_obfuscated": "L***e", "title": "Engineering Manager",
         "organization": {"name": "Acme"}, "has_email": True},
        "not-a-person",
    ]})

    people = dm.decision_maker_engine.search_apollo_people("https://acme.com", location="Prishtina", limit=50)

    url, kwargs = calls[0]
    assert url == "https://api.apollo.io/api/v1/mixed_people/api_search"
    assert kwargs["headers"]["x-api-key"] == "apollo-key"
    assert ("q_organization_domains_list[]", "acme.com") in kwargs["params"]
    assert ("person_locations[]", "Prishtina") in kwargs["params"]
    assert ("person_seniorities[]", "director") in kwargs["params"]
    assert ("per_page", dm.APOLLO_MAX_RESULTS) in kwargs["params"]
    assert people == [{
        "first_name": "Ada", "last_name_obfuscated": "L***e", "title": "Engineering Manager",
        "company": "Acme", "has_email": True,
    }]


def test_apollo_without_key_never_calls_the_network(monkeypatch):
    calls = _apollo(monkeypatch, key="")
    with pytest.raises(dm.ApolloError, match="ayarlı değil"):
        dm.decision_maker_engine.search_apollo_people("acme.com")
    assert calls == []


@pytest.mark.parametrize("status, fragment", [(401, "geçersiz"), (403, "erişimi yok"), (429, "sınırına"), (500, "HTTP 500")])
def test_apollo_failures_become_readable_errors(monkeypatch, status, fragment):
    _apollo(monkeypatch, status=status, body={"error": "nope"})
    with pytest.raises(dm.ApolloError, match=fragment):
        dm.decision_maker_engine.search_apollo_people("acme.com")


def test_search_endpoint_reports_missing_key_bad_domain_and_results(monkeypatch):
    client = TestClient(app)
    _apollo(monkeypatch, key="")
    assert client.post("/api/decision-makers/search", json={"company_domain": "acme.com"}).status_code == 503

    _apollo(monkeypatch, body={"people": [{"first_name": "Ada", "title": "CTO"}]})
    assert client.post("/api/decision-makers/search", json={"company_domain": "not a domain"}).status_code == 422
    response = client.post("/api/decision-makers/search", json={"company_domain": "acme.com"})
    assert response.status_code == 200
    assert response.json()["people"][0]["title"] == "CTO"


def test_proxy_url_becomes_playwright_proxy_settings():
    assert proxy_settings("") is None
    assert proxy_settings("http://proxy.example.com:8080") == {"server": "http://proxy.example.com:8080"}
    assert proxy_settings("socks5://user:p%40ss@10.0.0.1:1080") == {
        "server": "socks5://10.0.0.1:1080", "username": "user", "password": "p@ss",
    }


@pytest.mark.parametrize("bad", ["proxy.example.com:8080", "ftp://proxy.example.com", "http://"])
def test_malformed_proxy_url_fails_closed(bad):
    with pytest.raises(ValueError):
        proxy_settings(bad)
