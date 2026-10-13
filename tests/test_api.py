from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_expected_api_routes_are_registered():
    schema = app.openapi()
    paths = schema["paths"]

    expected_routes = {
        "/ai/chat",
        "/agent/run",
        "/auth/login",
        "/auth/me",
        "/incidents",
        "/incidents/{incident_id}",
    }

    assert expected_routes.issubset(paths.keys())
