import sqlite3

from backend.app.api.routers import trust
from backend.app.api.routers.trust import FeedbackRequest
from backend.app.api.routers.intelligence import SalaryAddRequest
from backend.app.core.tenant import get_tenant_id, reset_tenant_id, set_tenant_id
from backend.app.modules.rank.salary_lookup import SalaryLookup, assess_salary_evidence
from backend.app.modules.rank.salary_benchmark import calculate_salary_benchmark


def test_salary_evidence_score_is_metadata_completeness_not_verification():
    empty = assess_salary_evidence({})
    assert empty["score"] == 0
    assert empty["level"] == "limited_evidence"
    assert empty["independently_verified"] is False

    documented = assess_salary_evidence({
        "source_name": "Company compensation page",
        "source_url": "https://example.test/salary",
        "as_of": "2026-01-15",
        "sample_size": 12,
        "source_count": 2,
    })
    assert documented["score"] == 100
    assert documented["level"] == "well_documented"
    assert documented["independently_verified"] is False


def test_salary_lookup_is_isolated_per_tenant(tmp_path):
    lookup = SalaryLookup(tmp_path / "salary_data.json")
    tenant_token = set_tenant_id("salary-user-a")
    try:
        lookup.add_company("Example Co", salary_median=100000, source_name="User report")
        lookup.data_path.unlink()
        lookup.reload_current()
        assert lookup.stats()["total_companies"] == 0
    finally:
        reset_tenant_id(tenant_token)

    tenant_token = set_tenant_id("salary-user-b")
    try:
        assert lookup.search("Example Co") == []
    finally:
        reset_tenant_id(tenant_token)


def test_salary_api_validates_provenance_fields_and_benchmarks_are_labeled_estimates():
    request = SalaryAddRequest(
        company="Example Co", source_type="company_disclosed",
        source_name="Careers page", source_url="https://example.test/pay",
        as_of="2026-01-01", sample_size=8,
    )
    assert request.source_type == "company_disclosed"

    try:
        SalaryAddRequest(company="Example Co", source_url="javascript:alert(1)")
        assert False, "Unsafe source URLs must be rejected"
    except ValueError:
        pass

    estimate = calculate_salary_benchmark("Senior Developer", "Remote", 6)
    assert estimate["source_type"] == "modeled_estimate"
    assert estimate["is_company_reported"] is False
    assert estimate["evidence_level"] == "estimate_only"

def test_company_feedback_upserts_and_is_tenant_scoped(tmp_path, monkeypatch):
    original_get_tenant_id = get_tenant_id

    def connect_for_current_tenant():
        tenant_id = original_get_tenant_id() or "single-user"
        db_path = tmp_path / f"{tenant_id}.db"
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("CREATE TABLE IF NOT EXISTS scraped_jobs (id TEXT PRIMARY KEY, company TEXT, url TEXT)")
        connection.execute("INSERT OR IGNORE INTO scraped_jobs(id, company, url) VALUES ('job-1', 'Example Co', 'https://example.test/job')")
        connection.commit()
        return connection

    monkeypatch.setattr(trust, "get_db_connection", connect_for_current_tenant)
    request = FeedbackRequest(job_id="job-1", company="ignored", feedback_type="salary_mismatch", note="Range is incorrect")

    tenant_token = set_tenant_id("feedback-user-a")
    try:
        trust.save_feedback(request)
        trust.save_feedback(request.model_copy(update={"note": "Updated note"}))
        own_feedback = trust.get_feedback(job_id="job-1")
        assert own_feedback["scope"] == "your_account_only"
        assert own_feedback["feedback_types"] == ["salary_mismatch"]
        assert own_feedback["feedback"][0]["note"] == "Updated note"
        trust.save_feedback(request.model_copy(update={"feedback_type": "salary_consistent", "note": "Actually accurate"}))
        corrected = trust.get_feedback(job_id="job-1")
        assert corrected["feedback_types"] == ["salary_consistent"]
        trust.delete_feedback("salary_consistent", job_id="job-1")
        assert trust.get_feedback(job_id="job-1")["feedback"] == []
    finally:
        reset_tenant_id(tenant_token)


def test_feedback_endpoints_are_registered():
    from backend.app.main import app

    paths = app.openapi()["paths"]
    assert "/api/trust/feedback" in paths
    assert "get" in paths["/api/trust/feedback"]
    assert "post" in paths["/api/trust/feedback"]
    assert "/api/trust/feedback/{feedback_type}" in paths

    tenant_token = set_tenant_id("feedback-user-b")
    try:
        assert trust.get_feedback(job_id="job-1")["feedback"] == []
    finally:
        reset_tenant_id(tenant_token)
