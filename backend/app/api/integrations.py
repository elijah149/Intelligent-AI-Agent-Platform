import httpx
from fastapi import APIRouter, Depends, HTTPException

from backend.app.auth.rbac import require_permission
from backend.app.integrations.registry import (
    get_integration,
    list_integrations,
)
from backend.app.models.database import User


router = APIRouter(
    prefix="/integrations",
    tags=["Integrations"],
    dependencies=[Depends(require_permission("integration.call_api"))],
)


@router.get("")
async def get_integrations():
    """List integrations registered by the application."""
    return {
        "integrations": list_integrations(),
        "count": len(list_integrations()),
    }


@router.get("/{name}/health")
async def check_integration_health(name: str):
    """Check the health endpoint of a registered integration."""
    try:
        integration = get_integration(name)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Integration not found.",
        )

    if "GET" not in integration.allowed_methods:
        raise HTTPException(
            status_code=403,
            detail="GET is not allowed for this integration.",
        )

    url = integration.base_url.rstrip("/") + "/health"

    try:
        async with httpx.AsyncClient(
            timeout=5.0,
            follow_redirects=False,
        ) as client:
            response = await client.get(url)

        return {
            "integration": integration.name,
            "reachable": response.is_success,
            "status_code": response.status_code,
        }
    except httpx.RequestError:
        return {
            "integration": integration.name,
            "reachable": False,
            "message": "Integration health check failed.",
        }
