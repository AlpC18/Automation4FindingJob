"""The residential proxy setting for browser automation."""

import pytest

from backend.app.modules.scrape.stealth_browser import proxy_settings


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
