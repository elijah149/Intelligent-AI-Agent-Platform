from fastapi import Depends, HTTPException, status

from backend.app.auth.dependencies import get_current_user
from backend.app.models.database import User


ROLE_PERMISSIONS = {
    "customer": {
        "account.view_own",
    },
    "support_agent": {
        "agent.run",
        "account.view",
        "incident.create",
        "incident.view",
        "incident.diagnose",
        "account.unlock",
        "incident.verify",
        "incident.resolve",
    },
    "admin": {
        "agent.run",
        "account.view",
        "incident.create",
        "incident.view",
        "incident.diagnose",
        "account.unlock",
        "incident.verify",
        "incident.resolve",
        "integration.call_api",
        "user.manage",
        "system.manage",
        "audit.view",
    },
    "system_agent": {
        "agent.run",
        "account.view",
        "incident.create",
        "incident.view",
        "incident.diagnose",
        "account.unlock",
        "incident.verify",
        "incident.resolve",
    },
}


def get_user_permissions(user: User) -> set[str]:
    """Return a copy of permissions assigned to the user's role."""
    return set(ROLE_PERMISSIONS.get(user.role, set()))


def has_permission(user: User, permission: str) -> bool:
    return permission in get_user_permissions(user)


def require_role(*allowed_roles: str):
    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return current_user

    return role_checker


def require_permission(permission: str):
    def permission_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' is required.",
            )
        return current_user

    return permission_checker
