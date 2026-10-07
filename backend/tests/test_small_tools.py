"""Job keys, the company research cache, the plain-text CV and outgoing chat webhooks."""

import asyncio
import json
from datetime import datetime, timedelta

from backend.app.modules.apply import company_cache as cache_module
from backend.app.modules.setup.cv_cleaner import clean_raw_cv_text, convert_to_ats_standard
from backend.app.tools.job_key import audit_keys, make_job_key, slugify


def test_job_keys_are_stable_readable_and_distinct():
    assert make_job_key("Acme Corp", "Senior Engineer (L2)") == "acme-corp_senior-engineer-l2"
    assert slugify("Çığtekin İş") == "cgtekin-is"
    long_a = make_job_key("Acme", "Engineer " * 12 + "A")
    long_b = make_job_key("Acme", "Engineer " * 12 + "B")
    assert long_a != long_b and len(long_a) < 80


def test_job_keys_survive_non_latin_and_missing_text():
    assert make_job_key("株式会社", "エンジニア", "https://jobs.test/view/1234567") .endswith("_1234567")
    assert make_job_key("株式会社", "エンジニア").startswith("company-") and "_title-" in make_job_key("株式会社", "エンジニア")
    assert make_job_key("", "") == "unknown-company_unknown-title"


def test_key_audit_finds_collisions_and_unsafe_characters():
    audit = audit_keys([
        {"id": 1, "company": "Acme", "title": "Engineer"},
        {"id": 2, "company": "ACME", "title": "engineer"},
        {"id": 3, "company": "A/B Testing Ltd", "title": "Analyst"},
    ])

    assert (audit["total_jobs"], audit["unique_keys"], audit["collision_count"], audit["bad_char_count"]) == (3, 2, 1, 1)


def test_company_research_is_cached_until_it_expires(monkeypatch, tmp_path):
    monkeypatch.setattr(cache_module, "CACHE_DIR", tmp_path)
    cache = cache_module.CompanyResearchCache(ttl_days=7)
    calls = []

    def research(name, depth=1):
        calls.append((name, depth))
        return {"summary": f"About {name}"}

    first = cache.get_or_research("Acme & Sons", research, depth=2)
    second = cache.get_or_research("Acme & Sons", research, depth=2)

    assert first["summary"] == second["summary"] == "About Acme & Sons"
    assert calls == [("Acme & Sons", 2)]
    assert [entry["company"] for entry in cache.list_cached()] == ["Acme & Sons"]

    path = next(tmp_path.glob("*.json"))
    stale = json.loads(path.read_text(encoding="utf-8"))
    stale["_cached_at"] = (datetime.now() - timedelta(days=30)).isoformat()
    path.write_text(json.dumps(stale), encoding="utf-8")

    assert cache.get("Acme & Sons") is None
    assert cache.stats()["expired_entries"] == 1
    assert cache.invalidate("Acme & Sons") is True and cache.invalidate("Acme & Sons") is False
    assert cache.get_or_research("Nobody", lambda name: None) == {}


def test_unreadable_cache_entries_are_ignored(monkeypatch, tmp_path):
    monkeypatch.setattr(cache_module, "CACHE_DIR", tmp_path)
    (tmp_path / "broken.json").write_text("{nope", encoding="utf-8")
    (tmp_path / "odd-date.json").write_text('{"_cached_at": "yesterday"}', encoding="utf-8")
    cache = cache_module.CompanyResearchCache()

    assert cache.get("broken") is None and cache.get("odd date") is None
    assert cache.list_cached() == [{"company": "odd-date", "cached_at": "yesterday", "file": "odd-date.json"}]
    assert cache.stats()["expired_entries"] == 2
    assert len(cache_module._company_cache_key("x" * 100)) < 70 and cache_module._company_cache_key("!!!") == "unknown"


def test_raw_cv_text_is_tidied_without_losing_turkish_letters():
    raw = "Yüksel  Çığtekin\n\n\n\n• Python\n✓ SQL \U0001F600\n"

    assert clean_raw_cv_text(raw) == "Yüksel  Çığtekin\n\n- Python\n- SQL"
    assert clean_raw_cv_text("") == ""


def test_plain_text_cv_contains_only_what_the_profile_holds():
    full = convert_to_ats_standard({
        "full_name": "Ada Example", "email": "ada@example.test", "location": "Prishtina", "summary": "Backend developer.",
        "skills": ["Python", "SQL"],
        "experience": [{"title": "Developer", "company": "Acme", "period": "2024 - 2025", "bullets": ["Built the billing API"]}],
        "education": [{"degree": "BSc Computer Science", "school": "UP", "year": "2024"}],
    })
    sparse = convert_to_ats_standard({"full_name": "Ada Example", "experience": [{"company": "Acme"}], "education": [{"school": "UP"}]})

    assert "ADA EXAMPLE\nada@example.test | Prishtina" in full
    assert "DEVELOPER - ACME   [2024 - 2025]\n  - Built the billing API" in full
    assert "BSc Computer Science - UP (2024)" in full
    for invented in ("SOFTWARE ENGINEER", "2022 - Present", "Bachelor's Degree", "University", "2023", "CANDIDATE"):
        assert invented not in sparse
    assert "ACME" in sparse and "UP" in sparse
