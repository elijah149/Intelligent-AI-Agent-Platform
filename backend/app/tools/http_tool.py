import httpx

from backend.app.integrations.registry import get_integration


async def call_rest_api(
    integration: str,
    method: str,
    path: str = "/",
    payload: dict | None = None,
    headers: dict | None = None,
) -> dict:

    method = method.upper()

    try:
        selected_integration = get_integration(
            integration
        )
    except ValueError as exc:
        return {
            "success": False,
            "message": str(exc),
        }

    if method not in selected_integration.allowed_methods:
        return {
            "success": False,
            "message": (
                f"HTTP method '{method}' is not allowed "
                f"for integration '{integration}'."
            ),
        }

    if not path.startswith("/"):
        path = f"/{path}"

    url = (
        selected_integration.base_url.rstrip("/")
        + path
    )

    try:
        async with httpx.AsyncClient(
            timeout=30.0
        ) as client:

            response = await client.request(
                method=method,
                url=url,
                json=payload,
                headers=headers,
            )

        try:
            response_data = response.json()
        except ValueError:
            response_data = response.text

        return {
            "success": response.is_success,
            "status_code": response.status_code,
            "integration": integration,
            "method": method,
            "path": path,
            "url": url,
            "response": response_data,
        }

    except httpx.RequestError as exc:
        return {
            "success": False,
            "integration": integration,
            "method": method,
            "path": path,
            "url": url,
            "message": (
                f"REST API request failed: {str(exc)}"
            ),
        }
