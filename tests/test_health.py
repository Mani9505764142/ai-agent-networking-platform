"""
Tests for the root and health-check endpoints.

Verifies that the core application boots correctly
and responds with the expected payloads.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestRootEndpoint:
    """Tests for GET /"""

    def test_root_returns_200(self):
        response = client.get("/")
        assert response.status_code == 200

    def test_root_response_body(self):
        response = client.get("/")
        data = response.json()
        assert data["message"] == "AI Agent Networking Platform API"
        assert data["status"] == "running"


class TestHealthEndpoint:
    """Tests for GET /health"""

    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_body(self):
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert data["application"] == "AI Agent Networking Platform"
