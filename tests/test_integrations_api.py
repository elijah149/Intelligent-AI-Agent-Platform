from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.main import app
from backend.app.models.database import User


client = TestClient(app)


def fake_user(role: str) -> User:
    return User(
        id=1,
        username=f"test_{role}",
        password_hash="not-a-real-password-hash",
        role=role,
        is_active=True,
    )


def test_integrations_requires_authentication():
    response = client.get("/integrations")
    assert response.status_code == 401


def test_customer_cannot_list_integrations():
    app.dependency_overrides[get_current_user] = (
        lambda: fake_user("customer")
    )
    try:
        response = client.get("/integrations")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_admin_can_list_registered_integrations():
    app.dependency_overrides[get_current_user] = (
        lambda: fake_user("admin")
    )
    try:
        response = client.get("/integrations")
        assert response.status_code == 200
        body = response.json()
        assert body["count"] >= 1
        assert any(
            item["name"] == "local_health"
            for item in body["integrations"]
        )
    finally:
        app.dependency_overrides.clear()


def test_unknown_integration_health_returns_404():
    app.dependency_overrides[get_current_user] = (
        lambda: fake_user("admin")
    )
    try:
        response = client.get("/integrations/not_registered/health")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_health_check_uses_registered_base_url():
    app.dependency_overrides[get_current_user] = (
        lambda: fake_user("admin")
    )
    try:
        mock_response = type(
            "Response",
            (),
            {"is_success": True, "status_code": 200},
        )()

        with patch(
            "backend.app.api.integrations.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.get = (
                AsyncMock(return_value=mock_response)
            )

            response = client.get(
                "/integrations/local_health/health"
            )

        assert response.status_code == 200
        assert response.json()["reachable"] is True
        mock_client.return_value.__aenter__.return_value.get.assert_awaited_once_with(
            "http://127.0.0.1:47709/health"
        )
    finally:
        app.dependency_overrides.clear()
