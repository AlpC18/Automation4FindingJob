import os
import tempfile
import pytest
from pathlib import Path

# Ensure test environment before importing app modules
os.environ["ENVIRONMENT"] = "test"
os.environ["DEMO_DATA_ENABLED"] = "false"
os.environ["STARTUP_SEED_ENABLED"] = "false"
os.environ["AUTO_START_DAEMON"] = "false"

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import init_db, init_auth_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Ensure databases are initialized for test session."""
    init_db()
    init_auth_db()
    yield


@pytest.fixture
def client():
    """FastAPI test client fixture."""
    with TestClient(app) as test_client:
        yield test_client
