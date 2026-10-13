from collections.abc import Iterable

from backend.app.agents.tool_registry import get_tool
from backend.app.agents.authorization import authorization_policy


class ExecutionPolicy:
    """Additional safety rules for agent tool execution."""

    def can_execute(
        self,
        tool_name: str,
        history: list,
        authorized: bool = False,
        permissions: Iterable[str] | None = None,
    ) -> tuple[bool, str, str | None]:
        tool = get_tool(tool_name)

        # Check the tool's specific permission, not a global
        # authorization flag shared across unrelated actions.
        if not authorization_policy.can_execute(
            tool_name=tool_name,
            authorized=authorized,
            permissions=permissions,
        ):
            return (
                False,
                f"Permission required to execute tool '{tool_name}'.",
                None,
            )

        # Mutating tools require account investigation first.
        if not tool["read_only"]:
            has_investigation = any(
                item.get("execution", {}).get("tool")
                == "get_customer_account"
                and item.get("execution", {}).get("success")
                for item in history
            )

            if not has_investigation:
                return (
                    False,
                    (
                        f"Tool '{tool_name}' cannot be executed "
                        "before successful account investigation."
                    ),
                    "get_customer_account",
                )

        return True, "Execution allowed.", None


execution_policy = ExecutionPolicy()
