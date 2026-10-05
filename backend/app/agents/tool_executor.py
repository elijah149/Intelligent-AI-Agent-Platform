from sqlalchemy.orm import Session

from backend.app.agents.tool_registry import get_tool
from backend.app.agents.authorization import authorization_policy


class ToolExecutionError(Exception):
    """Raised when a tool cannot be executed."""
    pass


def execute_tool(
    db: Session,
    tool_name: str,
    parameters: dict,
    authorized: bool = False,
) -> dict:
    """
    Execute a registered tool through the authorization policy.
    """

    # 1. Retrieve registered tool
    try:
        tool = get_tool(tool_name)
    except ValueError as exc:
        raise ToolExecutionError(str(exc)) from exc

    # 2. Ask authorization policy
    allowed = authorization_policy.can_execute(
        tool_name=tool_name,
        authorized=authorized,
    )

    if not allowed:
        return {
            "success": False,
            "tool": tool_name,
            "message": (
                f"Execution of '{tool_name}' was denied "
                "by the authorization policy."
            ),
        }

    # 3. Get actual function
    function = tool["function"]

    # 4. Add database session
    parameters = {
        "db": db,
        **parameters,
    }

    # 5. Execute tool
    try:
        result = function(**parameters)

    except Exception as exc:
        return {
            "success": False,
            "tool": tool_name,
            "message": f"Tool execution failed: {str(exc)}",
        }

    # 6. Return standardized result
    return {
        "success": True,
        "tool": tool_name,
        "result": result,
    }
