"""Salary data the user enters, and job search without an external vector service."""

from datetime import date, timedelta

import pytest

from backend.app.modules.rank import semantic_search as search_module
from backend.app.modules.rank.salary_lookup import SalaryLookup, assess_salary_evidence


@pytest.fixture
def salaries(tmp_path):
    lookup = SalaryLookup(data_path=tmp_path / "salary.json")
    lookup.add_company("Gjirafa Labs Ltd", city="Prishtinë", salary_min=12000, salary_median=18000, salary_max=24000, currency="EUR")
    lookup.add_company("Acme Software GmbH", city="Berlin", salary_min=50000, salary_max=70000, currency="EUR", notes="Self-reported")
    return lookup


def test_company_search_tolerates_spelling_suffixes_and_diacritics(salaries):
    assert [entry["company"] for entry in salaries.search("gjirafa labs ltd")] == ["Gjirafa Labs Ltd"]
    assert salaries.search("Gjirafa")[0]["company"] == "Gjirafa Labs Ltd"
    assert salaries.search("Gjirafa Labs Ltd Kosovo Branch")[0]["company"] == "Gjirafa Labs Ltd"
    assert salaries.search("Software Acme")[0]["company"] == "Acme Software GmbH"
    assert salaries.search("Acme", city="Prishtine") == []
    assert salaries.search("Gjirafa", city="prishtine")[0]["city"] == "Prishtinë"
    assert salaries.search("Nonexistent") == []
    assert SalaryLookup(data_path=salaries.data_path.parent / "empty.json").search("Acme") == []


def test_adding_the_same_company_updates_it_and_persists(salaries):
    result = salaries.add_company("gjirafa labs ltd", city="Prishtinë", salary_median=20000)
    reopened = SalaryLookup(data_path=salaries.data_path)

    assert result["action"] == "updated"
    stats = reopened.stats()
    assert (stats["total_companies"], stats["unique_cities"], sorted(stats["currencies"])) == (2, 2, ["EUR", "USD"])
    assert reopened.search("Gjirafa")[0]["salary_median"] == 20000


def test_bulk_import_counts_added_updated_and_failed(salaries):
    result = salaries.import_from_list([
        {"company": "New Co", "salary_min": 1, "salary_max": 2},
        {"company": "Acme Software GmbH", "city": "Berlin"},
        {"company": "Broken Co", "source_name": None},
    ])

    assert (result["added"], result["updated"], result["errors"]) == (1, 1, 1)


def test_validation_reports_impossible_ranges(salaries):
    salaries.add_company("Upside Down", salary_min=90, salary_median=10, salary_max=50)
    salaries.add_company("", salary_median=99, salary_max=50)

    report = salaries.validate()

    assert report["is_valid"] is False
    assert "Upside Down: min (90) > max (50)" in report["errors"] and any("missing company name" in e for e in report["errors"])
    assert report["warning_count"] == 2


def test_entries_are_formatted_for_reading(salaries):
    text = salaries.format_entry(salaries.search("Acme")[0])

    assert "Acme Software GmbH (Berlin)" in text and "Range: EUR 50,000 – 70,000 / year" in text and "Note: Self-reported" in text
    assert "Median: EUR 18,000 / year" in salaries.format_entry(salaries.search("Gjirafa")[0])


def test_evidence_score_reflects_documentation_not_truth():
    documented = assess_salary_evidence({
        "source_name": "Survey", "source_url": "https://survey.test/2026", "as_of": date.today().isoformat(),
        "sample_size": 12, "source_count": 2,
    })
    aging = assess_salary_evidence({"as_of": (date.today() - timedelta(days=500)).isoformat(), "sample_size": 5})
    bare = assess_salary_evidence({"source_url": "not a url", "as_of": "last spring", "sample_size": 0})

    assert (documented["score"], documented["level"], documented["freshness"]) == (100, "well_documented", "current")
    assert (aging["score"], aging["freshness"]) == (25, "aging")
    assert (bare["score"], bare["level"], bare["freshness"]) == (0, "limited_evidence", "unknown")
    assert assess_salary_evidence({"as_of": "2019-01-01"})["freshness"] == "outdated"
    assert documented["independently_verified"] is False


JOBS = {
    "a": {"title": "Python Backend Developer", "company": "Acme", "location": "Remote", "description": "FastAPI, Docker and good Go skills", "match_score": 80},
    "b": {"title": "React Developer", "company": "Globex", "location": "Berlin", "description": "TypeScript at Google scale"},
    "c": {"title": "Accountant", "company": "Initech", "location": "Prishtina"},
}


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setattr(search_module, "feed_jobs", lambda: JOBS)
    search = search_module.SemanticSearchEngine.__new__(search_module.SemanticSearchEngine)
    search.client = search.collection = search.pg_connection = None
    search.backend = "fallback"
    return search


def test_search_falls_back_to_keywords_without_a_vector_store(engine):
    assert [job["company"] for job in engine.semantic_search("python developer")] == ["Acme", "Globex"]
    assert engine.semantic_search("developer", limit=1)[0]["company"] == "Acme"
    assert engine.semantic_search("plumber") == []
    assert engine.index_all_seen_jobs()["status"] == "error"


class FakeCollection:
    def __init__(self):
        self.rows = {}

    def upsert(self, documents, metadatas, ids):
        self.rows = dict(zip(ids, metadatas))

    def count(self):
        return len(self.rows)

    def query(self, query_texts, n_results):
        ids = list(self.rows)[:n_results]
        return {"ids": [ids], "metadatas": [[self.rows[key] for key in ids]], "distances": [[0.1 * (index + 1) for index in range(len(ids))]]}


def test_search_uses_the_vector_store_when_it_is_available(engine):
    engine.collection = FakeCollection()

    indexed = engine.index_all_seen_jobs()
    matches = engine.semantic_search("backend", limit=2)
    similar = engine.find_similar_jobs("a", limit=5)

    assert indexed == {"status": "success", "indexed_count": 3, "total_tracked": 3}
    assert [(match["job_key"], match["semantic_similarity"]) for match in matches] == [("a", 90.0), ("b", 80.0)]
    assert [match["job_key"] for match in similar] == ["b", "c"]
    assert engine.find_similar_jobs("missing") == []


def test_local_embeddings_are_stable_unit_vectors(engine):
    first, again, other = engine._embedding("Python FastAPI"), engine._embedding("python fastapi"), engine._embedding("React")

    assert first == again and first != other
    assert abs(sum(value * value for value in first) - 1.0) < 1e-9
    assert not any(engine._embedding(""))


def test_skill_trends_count_whole_words_only(engine):
    trends = engine.analyze_market_skill_trends()
    counts = {item["skill"]: item["count"] for item in trends["top_in_demand_skills"]}

    assert trends["total_analyzed_jobs"] == 3
    assert counts["Go"] == 1  # "good" and "Google" are not the Go language
    assert counts["Python"] == 1 and counts["React"] == 1 and "Kafka" not in counts
    assert trends["market_summary"].startswith("Son taranan 3 ilanda")
