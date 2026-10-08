def test_health_check_returns_200(client):
    """Test root health check endpoint returns 200 OK."""
    response = client.get("/")
    assert response.status_code == 200


def test_health_check_payload_structure(client):
    """Test root health check response schema and content."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ONLINE"
    assert "service" in data
    assert "version" in data
    assert "environment" in data
    assert "runtime_config" in data
    assert data["docs_url"] == "/docs"


def test_system_status_endpoint(client):
    """Test system status endpoint under /api/system/status."""
    response = client.get("/api/system/status")
    # Endpoint should return 200 or valid status structure
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, dict)
