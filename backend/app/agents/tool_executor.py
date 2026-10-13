import inspect
from collections.abc import Iterable

from sqlalchemy.orm import Session

from backend.app.agents.tool_registry import get_tool
from backend.app.agents.authorization import authorization_policy


class ToolExecutionError(Exception):
    """Raised when a tool cannot be executed."""


async def execute_tool(
    db: Session,
    tool_name: str,
    parameters: dict,
    authorized: bool = False,
    permissions: Iterable[str] | None = None,
    unlock_approved: bool = False,
) -> dict:
    """Execute a registered tool after checking its specific permission."""
    if tool_name == "unlock_account" and not unlock_approved:
        return {
            "success": False,
            "status": "awaiting_authorization",
            "tool": "unlock_account",
            "message": (
                "Account unlock requires explicit approval. "
                "Role permissions alone are not sufficient."
            ),
        }

    try:
        tool = get_tool(tool_name)
    except ValueError as exc:
        raise ToolExecutionError(str(exc)) from exc

    allowed = authorization_policy.can_execute(
        tool_name=tool_name,
        authorized=authorized,
        permissions=permissions,
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

    # Never trust an authorization value supplied by an LLM
    # or included in tool parameters.
    execution_parameters = {
        key: value
        for key, value in parameters.items()
        if key != "authorized"
    }

    # The unlock function has its own internal guard. Set that
    # guard only after the policy above has approved this action.

    function = tool["function"]

    if tool_name == "call_rest_api":
        call_parameters = execution_parameters
    else:
        call_parameters = {"db": db, **execution_parameters}

    try:
        result = function(**call_parameters)
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:
        return {
            "success": False,
            "tool": tool_name,
            "message": f"Tool execution failed: {str(exc)}",
        }

    if tool_name == "create_incident":
        return {
            "success": True,
            "tool": tool_name,
            "result": {
                "incident_id": result.id,
                "customer_id": result.customer_id,
                "issue": result.issue,
                "diagnosis": result.diagnosis,
                "status": result.status,
            },
        }

    return {
        "success": True,
        "tool": tool_name,
        "result": result,
    }
