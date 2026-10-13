from collections.abc import Iterable

from sqlalchemy.orm import Session

from backend.app.agents.tool_executor import execute_tool


class AgentDecisionEngine:
    """Determine the next action using explicit permissions."""

    async def analyze_account_issue(
        self,
        db: Session,
        username: str,
        incident_id: int,
        authorized: bool = False,
        permissions: Iterable[str] | None = None,
    ) -> dict:
        granted_permissions = set(permissions or ())

        # Legacy boolean is deliberately not trusted.
        account_result = await execute_tool(
            db=db,
            tool_name="get_customer_account",
            parameters={"username": username},
            permissions=granted_permissions,
        )

        if not account_result["success"]:
            return {
                "success": False,
                "stage": "investigation",
                "message": account_result["message"],
            }

        result = account_result["result"]

        if not result["found"]:
            return {
                "success": False,
                "stage": "investigation",
                "message": "Customer account was not found.",
            }

        account = result["account"]

        if account["is_locked"]:
            diagnosis = (
                f"Account '{username}' is locked with "
                f"{account['failed_login_attempts']} failed login attempts."
            )

            if "account.unlock" not in granted_permissions:
                return {
                    "success": True,
                    "stage": "authorization",
                    "next_action": "unlock_account",
                    "authorization_required": True,
                    "diagnosis": diagnosis,
                    "message": (
                        "The account is locked. "
                        "Unlocking requires account.unlock permission."
                    ),
                }

            action_result = await execute_tool(
                db=db,
                tool_name="unlock_account",
                parameters={
                    "username": username,
                    "incident_id": incident_id,
                },
                permissions=granted_permissions,
            )

            if not action_result["success"]:
                return {
                    "success": False,
                    "stage": "action",
                    "message": action_result["message"],
                }

            return {
                "success": True,
                "stage": "action",
                "next_action": "verify_incident_resolution",
                "diagnosis": diagnosis,
                "action": action_result["result"],
            }

        if account["status"] != "active":
            return {
                "success": True,
                "stage": "diagnosis",
                "next_action": "further_investigation",
                "diagnosis": (
                    f"Account '{username}' is not active. "
                    f"Current status: {account['status']}."
                ),
                "message": "The account requires further investigation.",
            }

        return {
            "success": True,
            "stage": "diagnosis",
            "next_action": "further_investigation",
            "diagnosis": f"Account '{username}' is active and not locked.",
            "message": (
                "The reported problem cannot be explained "
                "by the current account state."
            ),
        }


decision_engine = AgentDecisionEngine()
