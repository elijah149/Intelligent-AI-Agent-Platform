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


def test_agent_run_requires_authentication():
    response = client.post(
        "/agent/run",
        json={
            "customer_message": "I cannot log in",
            "username": "johnmwanga",
        },
    )

    assert response.status_code == 401


def test_customer_cannot_run_support_agent():
    app.dependency_overrides[get_current_user] = (
        lambda: fake_user("customer")
    )

    try:
        response = client.post(
            "/agent/run",
            json={
                "customer_message": "I cannot log in",
                "username": "johnmwanga",
            },
        )

        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_support_agent_can_run_agent_endpoint():
    app.dependency_overrides[get_current_user] = (
        lambda: fake_user("support_agent")
    )

    mocked_run = AsyncMock(
        return_value={
            "success": True,
            "status": "test_completed",
        }
    )

    try:
        with patch(
            "backend.app.api.agent.agent_loop.run",
            mocked_run,
        ):
            response = client.post(
                "/agent/run",
                json={
                    "customer_message": "I cannot log in",
                    "username": "johnmwanga",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "test_completed"

        call_kwargs = mocked_run.await_args.kwargs
        assert "account.unlock" in call_kwargs["permissions"]
        assert call_kwargs["actor_username"] == "test_support_agent"
    finally:
        app.dependency_overrides.clear()


def test_customer_cannot_gain_agent_access_by_sending_authorized_true():
    app.dependency_overrides[get_current_user] = (
        lambda: fake_user("customer")
    )

    try:
        response = client.post(
            "/agent/run",
            json={
                "customer_message": "Unlock my account",
                "username": "johnmwanga",
                "authorized": True,
            },
        )

        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_client_cannot_override_authorization_for_support_agent():
    app.dependency_overrides[get_current_user] = (
        lambda: fake_user("support_agent")
    )

    mocked_run = AsyncMock(
        return_value={
            "success": False,
            "status": "authorization_checked",
        }
    )

    try:
        with patch(
            "backend.app.api.agent.agent_loop.run",
            mocked_run,
        ):
            response = client.post(
                "/agent/run",
                json={
                    "customer_message": "I cannot log in",
                    "username": "johnmwanga",
                    "authorized": False,
                    "actor_username": "admin",
                },
            )

        assert response.status_code == 200

        call_kwargs = mocked_run.await_args.kwargs

        # Authorization and actor identity must come from
        # the authenticated server-side user, not the request body.
        assert "account.unlock" in call_kwargs["permissions"]
        assert call_kwargs["actor_username"] == "test_support_agent"
    finally:
        app.dependency_overrides.clear()
