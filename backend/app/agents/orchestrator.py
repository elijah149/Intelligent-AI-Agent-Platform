from collections.abc import Iterable

from sqlalchemy.orm import Session

from backend.app.agents.authorization import authorization_policy
from backend.app.agents.decision_engine import decision_engine
from backend.app.agents.tool_executor import execute_tool
from backend.app.services.incident_service import create_incident


class AgentOrchestrator:
    """Coordinate account-support workflow with explicit permissions."""

    async def handle_account_issue(
        self,
        db: Session,
        customer_id: int,
        username: str,
        issue: str,
        authorized: bool = False,
        permissions: Iterable[str] | None = None,
    ) -> dict:
        granted_permissions = set(permissions or ())

        if "incident.create" not in granted_permissions:
            return {
                "success": False,
                "stage": "authorization",
                "message": "Incident creation requires permission.",
            }

        incident = create_incident(
            db=db,
            customer_id=customer_id,
            issue=issue,
        )

        decision = await decision_engine.analyze_account_issue(
            db=db,
            username=username,
            incident_id=incident.id,
            permissions=granted_permissions,
        )

        if not decision["success"]:
            return {
                "success": False,
                "stage": decision.get("stage"),
                "incident_id": incident.id,
                "message": decision["message"],
            }

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

        if decision.get("next_action") == "verify_incident_resolution":
            if not authorization_policy.can_execute(
                "verify_incident_resolution",
                permissions=granted_permissions,
            ):
                return {
                    "success": False,
                    "stage": "authorization",
                    "incident_id": incident.id,
                    "message": "Incident verification requires permission.",
                }

            verification = await execute_tool(
                db=db,
                tool_name="verify_incident_resolution",
                parameters={
                    "incident_id": incident.id,
                    "username": username,
                },
                permissions=granted_permissions,
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

            if not authorization_policy.can_execute(
                "resolve_incident",
                permissions=granted_permissions,
            ):
                return {
                    "success": False,
                    "stage": "authorization",
                    "incident_id": incident.id,
                    "message": "Incident resolution requires permission.",
                }

            resolution = await execute_tool(
                db=db,
                tool_name="resolve_incident",
                parameters={
                    "incident_id": incident.id,
                    "username": username,
                },
                permissions=granted_permissions,
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

        return {
            "success": True,
            "stage": "investigation",
            "incident_id": incident.id,
            "status": "requires_further_investigation",
            "diagnosis": decision.get("diagnosis"),
            "message": decision.get("message"),
        }


agent_orchestrator = AgentOrchestrator()
