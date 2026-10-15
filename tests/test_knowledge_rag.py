from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.main import app
from backend.app.models.database import User


class FakeLLM:
    def __init__(self):
        self.last_prompt = ""

    async def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return "Test response"


def fake_support_agent() -> User:
    return User(
        id=1,
        username="test_support_agent",
        password_hash="not-a-real-password-hash",
        role="support_agent",
        is_active=True,
    )


def test_chat_requires_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/ai/chat",
            json={"message": "My account is locked"},
        )

    assert response.status_code == 401


def test_customer_cannot_access_chat():
    app.dependency_overrides[get_current_user] = lambda: User(
        id=2,
        username="test_customer",
        password_hash="not-a-real-password-hash",
        role="customer",
        is_active=True,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/ai/chat",
                json={"message": "My account is locked"},
            )

        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_chat_includes_retrieved_knowledge():
    document = {
        "id": 999,
        "title": "Locked Account Support Procedure",
        "source": "support-policy-demo",
        "content": (
            "Verify the customer's identity using the approved "
            "verification process before unlocking the account."
        ),
        "score": 0.9,
        "matched_terms": ["account", "locked"],
    }
    fake_llm = FakeLLM()
    app.dependency_overrides[get_current_user] = fake_support_agent

    try:
        with (
            patch(
                "backend.app.api.ai.retrieve_knowledge",
                return_value=[document],
            ),
            patch(
                "backend.app.api.ai.get_llm_provider",
                return_value=fake_llm,
            ),
            TestClient(app) as client,
        ):
            response = client.post(
                "/ai/chat",
                json={"message": "My account is locked"},
            )

        assert response.status_code == 200
        assert response.json()["response"] == "Test response"
        assert "KNOWLEDGE CONTEXT:" in fake_llm.last_prompt
        assert "Locked Account Support Procedure" in fake_llm.last_prompt
        assert "approved verification process" in fake_llm.last_prompt
    finally:
        app.dependency_overrides.clear()


def test_chat_handles_no_retrieved_knowledge():
    fake_llm = FakeLLM()
    app.dependency_overrides[get_current_user] = fake_support_agent

    try:
        with (
            patch(
                "backend.app.api.ai.retrieve_knowledge",
                return_value=[],
            ),
            patch(
                "backend.app.api.ai.get_llm_provider",
                return_value=fake_llm,
            ),
            TestClient(app) as client,
        ):
            response = client.post(
                "/ai/chat",
                json={"message": "How do I resolve an unusual problem?"},
            )

        assert response.status_code == 200
        assert "No relevant knowledge-base documents" in fake_llm.last_prompt
        assert "KNOWLEDGE CONTEXT:" not in fake_llm.last_prompt
    finally:
        app.dependency_overrides.clear()
