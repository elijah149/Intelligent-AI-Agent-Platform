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


def test_me_requires_authentication():
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_support_endpoint_requires_authentication():
    response = client.get("/auth/support-test")

    assert response.status_code == 401


def test_customer_cannot_access_support_endpoint():
    app.dependency_overrides[get_current_user] = (
        lambda: fake_user("customer")
    )

    try:
        response = client.get("/auth/support-test")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_support_agent_can_access_support_endpoint():
    app.dependency_overrides[get_current_user] = (
        lambda: fake_user("support_agent")
    )

    try:
        response = client.get("/auth/support-test")

        assert response.status_code == 200
        assert response.json()["role"] == "support_agent"
    finally:
        app.dependency_overrides.clear()


def test_customer_cannot_unlock_accounts_or_manage_incidents():
    from backend.app.auth.rbac import has_permission

    customer = fake_user("customer")

    assert has_permission(customer, "account.unlock") is False
    assert has_permission(customer, "incident.create") is False
    assert has_permission(customer, "incident.view") is False
    assert has_permission(customer, "agent.run") is False


def test_support_agent_has_expected_support_permissions():
    from backend.app.auth.rbac import has_permission

    support_agent = fake_user("support_agent")

    assert has_permission(support_agent, "agent.run") is True
    assert has_permission(support_agent, "account.unlock") is True
    assert has_permission(support_agent, "incident.create") is True
    assert has_permission(support_agent, "incident.view") is True
    assert has_permission(support_agent, "user.manage") is False


def test_unknown_role_has_no_permissions():
    from backend.app.auth.rbac import has_permission

    unknown_user = fake_user("unknown_role")

    assert has_permission(unknown_user, "agent.run") is False
    assert has_permission(unknown_user, "account.unlock") is False
