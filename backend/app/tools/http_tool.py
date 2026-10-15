import re

import httpx

from backend.app.integrations.registry import get_integration


SAFE_PATH_PATTERN = re.compile(r"^/[A-Za-z0-9/_-]*$")

ALLOWED_HEADERS = {
    "accept",
    "content-type",
}


def validate_path(path: str) -> str | None:
    """Accept only simple absolute paths, not URLs or traversal paths."""
    if not isinstance(path, str) or not path:
        return "Path must be a non-empty string."

    if len(path) > 200:
        return "Path is too long."

    if not SAFE_PATH_PATTERN.fullmatch(path):
        return "Path contains unsupported or unsafe characters."

    if "//" in path:
        return "Repeated slashes are not allowed."

    if any(part in {".", ".."} for part in path.split("/")):
        return "Path traversal is not allowed."

    return None


def validate_headers(headers: dict | None) -> str | None:
    if headers is None:
        return None

    if not isinstance(headers, dict):
        return "Headers must be a dictionary."

    for name, value in headers.items():
        if not isinstance(name, str) or name.lower() not in ALLOWED_HEADERS:
            return f"Header '{name}' is not allowed."

        if (
            not isinstance(value, str)
            or len(value) > 256
            or "\r" in value
            or "\n" in value
        ):
            return f"Invalid value for header '{name}'."

    return None


async def call_rest_api(
    integration: str,
    method: str,
    path: str = "/",
    payload: dict | None = None,
    headers: dict | None = None,
) -> dict:
    if not isinstance(method, str):
        return {"success": False, "message": "HTTP method must be a string."}

    method = method.upper()

    try:
        selected_integration = get_integration(integration)
    except ValueError as exc:
        return {"success": False, "message": str(exc)}

    if method not in selected_integration.allowed_methods:
        return {
            "success": False,
            "message": (
                f"HTTP method '{method}' is not allowed "
                f"for integration '{integration}'."
            ),
        }

    path_error = validate_path(path)
    if path_error:
        return {"success": False, "message": path_error}

    headers_error = validate_headers(headers)
    if headers_error:
        return {"success": False, "message": headers_error}

    if payload is not None and not isinstance(payload, dict):
        return {
            "success": False,
            "message": "Payload must be a dictionary.",
        }

    if method == "GET" and payload is not None:
        return {
            "success": False,
            "message": "GET requests must not include a payload.",
        }

    url = selected_integration.base_url.rstrip("/") + path

    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=False,
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
            response_data = response.text[:10_000]

        return {
            "success": response.is_success,
            "status_code": response.status_code,
            "integration": integration,
            "method": method,
            "path": path,
            "url": url,
            "response": response_data,
        }

    except httpx.RequestError:
        # Do not expose internal network details in error responses.
        return {
            "success": False,
            "integration": integration,
            "method": method,
            "path": path,
            "message": "REST API request failed.",
        }
