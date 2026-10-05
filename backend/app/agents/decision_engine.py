from sqlalchemy.orm import Session

from backend.app.agents.tool_executor import execute_tool


class AgentDecisionEngine:
    """
    Decision engine for determining what the AI agent
    should do based on the current incident state.
    """

    def analyze_account_issue(
        self,
        db: Session,
        username: str,
        incident_id: int,
        authorized: bool = False,
    ) -> dict:
        """
        Analyze an account-related problem and determine
        the next appropriate action.
        """

        # Step 1: Inspect account state
        account_result = execute_tool(
            db=db,
            tool_name="get_customer_account",
            parameters={
                "username": username,
            },
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

        # Step 2: Determine account state
        if account["is_locked"]:
            diagnosis = (
                f"Account '{username}' is locked with "
                f"{account['failed_login_attempts']} failed login attempts."
            )

            # Step 3: Authorization required
            if not authorized:
                return {
                    "success": True,
                    "stage": "authorization",
                    "next_action": "unlock_account",
                    "authorization_required": True,
                    "diagnosis": diagnosis,
                    "message": (
                        "The account is locked. "
                        "Unlocking the account requires authorization."
                    ),
                }

            # Step 4: Execute authorized action
            action_result = execute_tool(
                db=db,
                tool_name="unlock_account",
                parameters={
                    "username": username,
                    "incident_id": incident_id,
                    "authorized": True,
                },
                authorized=True,
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

        # Step 5: Account is not locked
        if account["status"] != "active":
            return {
                "success": True,
                "stage": "diagnosis",
                "next_action": "further_investigation",
                "diagnosis": (
                    f"Account '{username}' is not active. "
                    f"Current status: {account['status']}."
                ),
                "message": (
                    "The account requires further investigation."
                ),
            }

        return {
            "success": True,
            "stage": "diagnosis",
            "next_action": "further_investigation",
            "diagnosis": (
                f"Account '{username}' is active and not locked."
            ),
            "message": (
                "The reported problem cannot be explained "
                "by the current account state."
            ),
        }


decision_engine = AgentDecisionEngine()
