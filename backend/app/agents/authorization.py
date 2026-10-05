from backend.app.agents.tool_registry import get_tool


class AuthorizationPolicy:
    """
    Controls whether an AI agent is allowed to execute
    a particular tool.
    """

    def can_execute(
        self,
        tool_name: str,
        authorized: bool = False,
    ) -> bool:
        """
        Determine whether a tool can be executed.
        """

        tool = get_tool(tool_name)

        # Read-only tools do not require authorization.
        if tool["read_only"]:
            return True

        # Action tools marked as requiring authorization
        # must receive explicit authorization.
        if tool["requires_authorization"]:
            return authorized

        # Non-sensitive tools can execute normally.
        return True


authorization_policy = AuthorizationPolicy()
