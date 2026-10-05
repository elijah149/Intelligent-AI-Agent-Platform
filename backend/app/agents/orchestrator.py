from sqlalchemy.orm import Session

from backend.app.services.incident_service import create_incident
from backend.app.agents.decision_engine import decision_engine
from backend.app.agents.tool_executor import execute_tool


class AgentOrchestrator:
    """
    Coordinates the complete AI agent workflow.
    """

    def handle_account_issue(
        self,
        db: Session,
        customer_id: int,
        username: str,
        issue: str,
        authorized: bool = False,
    ) -> dict:
        # -------------------------------------------------
        # 1. UNDERSTAND
        # -------------------------------------------------

        incident = create_incident(
            db=db,
            customer_id=customer_id,
            issue=issue,
        )

        # -------------------------------------------------
        # 2. DIAGNOSE + DECIDE
        # -------------------------------------------------

        decision = decision_engine.analyze_account_issue(
            db=db,
            username=username,
            incident_id=incident.id,
            authorized=authorized,
        )

        if not decision["success"]:
            return {
                "success": False,
                "stage": decision.get("stage"),
                "incident_id": incident.id,
                "message": decision["message"],
            }

        # -------------------------------------------------
        # 3. AUTHORIZATION REQUIRED
        # -------------------------------------------------

        if decision.get("authorization_required"):
            return {
                "success": True,
                "stage": "authorization",
                "incident_id": incident.id,
                "status": "awaiting_authorization",
                "diagnosis": decision["diagnosis"],
                "next_action": decision["next_action"],
                "message": decision["message"],
            }

        # -------------------------------------------------
        # 4. ACTION
        # -------------------------------------------------

        if decision.get("next_action") == "verify_incident_resolution":

            verification = execute_tool(
                db=db,
                tool_name="verify_incident_resolution",
                parameters={
                    "incident_id": incident.id,
                },
            )

            if not verification["success"]:
                return {
                    "success": False,
                    "stage": "verification",
                    "incident_id": incident.id,
                    "message": verification["message"],
                }

            verification_result = verification["result"]

            if not verification_result["verified"]:
                return {
                    "success": False,
                    "stage": "verification",
                    "incident_id": incident.id,
                    "status": "verification_failed",
                    "message": verification_result["message"],
                }

            # -------------------------------------------------
            # 5. RESOLVE
            # -------------------------------------------------

            resolution = execute_tool(
                db=db,
                tool_name="resolve_incident",
                parameters={
                    "incident_id": incident.id,
                },
            )

            if not resolution["success"]:
                return {
                    "success": False,
                    "stage": "resolution",
                    "incident_id": incident.id,
                    "message": resolution["message"],
                }

            return {
                "success": True,
                "stage": "resolved",
                "incident_id": incident.id,
                "status": "resolved",
                "diagnosis": decision.get("diagnosis"),
                "action": decision.get("action"),
                "verification": verification_result["message"],
                "resolution": resolution["result"]["message"],
            }

        # -------------------------------------------------
        # 6. FURTHER INVESTIGATION
        # -------------------------------------------------

        return {
            "success": True,
            "stage": "investigation",
            "incident_id": incident.id,
            "status": "requires_further_investigation",
            "diagnosis": decision.get("diagnosis"),
            "message": decision.get("message"),
        }


agent_orchestrator = AgentOrchestrator()
