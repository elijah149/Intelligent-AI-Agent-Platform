from backend.app.agents.tool_registry import get_tool


class ExecutionPolicy:
    """
    Additional safety rules for agent tool execution.
    """

    def can_execute(
        self,
        tool_name: str,
        history: list,
        authorized: bool = False,
    ) -> tuple[bool, str, str | None]:

        tool = get_tool(tool_name)

        # -------------------------------------------------
        # Rule 1: Protected actions require authorization
        # -------------------------------------------------

        if tool["requires_authorization"] and not authorized:
            return (
                False,
                f"Tool '{tool_name}' requires authorization.",
                None,
            )

        # -------------------------------------------------
        # Rule 2: Action tools require investigation first
        # -------------------------------------------------

        if not tool["read_only"]:

            has_investigation = any(
                item.get("execution", {}).get("tool")
                == "get_customer_account"
                for item in history
            )

            if not has_investigation:
                return (
                    False,
                    (
                        f"Tool '{tool_name}' cannot be executed "
                        "before account investigation."
                    ),
                    "get_customer_account",
                )

        return True, "Execution allowed.", None


execution_policy = ExecutionPolicy()
