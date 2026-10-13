from collections.abc import Iterable

from backend.app.agents.tool_registry import get_tool


class AuthorizationPolicy:
    """Authorize each tool using its specific permission."""

    def can_execute(
        self,
        tool_name: str,
        authorized: bool = False,
        permissions: Iterable[str] | None = None,
    ) -> bool:
        tool = get_tool(tool_name)
        required_permission = tool.get("required_permission")

        # A legacy boolean is not proof of an authenticated permission.
        # Only explicit permissions supplied by trusted server-side RBAC count.
        granted = set(permissions or ())

        # Check the required permission before read-only handling.
        # Some read-only investigation tools are still permission-protected.
        if required_permission is not None:
            return required_permission in granted

        # Tools without a required permission retain their existing policy.
        return True


authorization_policy = AuthorizationPolicy()
