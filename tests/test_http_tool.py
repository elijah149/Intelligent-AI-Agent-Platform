import pytest

from backend.app.integrations.registry import get_integration
from backend.app.tools.http_tool import call_rest_api


@pytest.mark.asyncio
async def test_unregistered_integration_is_rejected():
    result = await call_rest_api(
        integration="unknown_system",
        method="GET",
        path="/health",
    )

    assert result["success"] is False
    assert "not registered" in result["message"]


@pytest.mark.asyncio
async def test_disallowed_method_is_rejected():
    integration = get_integration("local_health")
    assert "POST" not in integration.allowed_methods

    result = await call_rest_api(
        integration="local_health",
        method="POST",
        path="/health",
    )

    assert result["success"] is False
    assert "not allowed" in result["message"]


@pytest.mark.asyncio
async def test_invalid_integration_does_not_make_http_request():
    result = await call_rest_api(
        integration="malicious_system",
        method="GET",
        path="/health",
    )

    assert result == {
        "success": False,
        "message": "Integration 'malicious_system' is not registered.",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unsafe_path",
    [
        "https://example.com",
        "//example.com/health",
        "/../admin",
        "/health/../admin",
        "/health?token=secret",
        "/health#fragment",
        "/health%2f..%2fadmin",
        "/health\\admin",
    ],
)
async def test_unsafe_paths_are_rejected(unsafe_path):
    result = await call_rest_api(
        integration="local_health",
        method="GET",
        path=unsafe_path,
    )

    assert result["success"] is False
    assert "Path" in result["message"]


@pytest.mark.asyncio
async def test_sensitive_headers_are_rejected():
    result = await call_rest_api(
        integration="local_health",
        method="GET",
        path="/health",
        headers={"Authorization": "Bearer secret"},
    )

    assert result["success"] is False
    assert "not allowed" in result["message"]


@pytest.mark.asyncio
async def test_get_payload_is_rejected():
    result = await call_rest_api(
        integration="local_health",
        method="GET",
        path="/health",
        payload={"admin": True},
    )

    assert result["success"] is False
    assert "GET" in result["message"]
