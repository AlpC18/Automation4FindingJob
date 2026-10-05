from fastapi.testclient import TestClient

from backend.app.main import app


def test_prometheus_metrics_report_http_requests_and_latency():
    client = TestClient(app)
    response = client.get("/api/system/health")
    assert response.status_code == 200

    metrics = client.get("/api/system/metrics")
    assert metrics.status_code == 200
    assert "career_agent_http_requests_total" in metrics.text
    assert 'route="/system/health"' in metrics.text
    assert "career_agent_http_request_duration_seconds_bucket" in metrics.text
    assert "# TYPE career_agent_http_request_duration_seconds histogram" in metrics.text
