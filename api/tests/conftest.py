import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """HTTP client bound to the FastAPI app; no real network involved."""
    return TestClient(app)
