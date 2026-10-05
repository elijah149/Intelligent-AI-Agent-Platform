from sqlalchemy.orm import Session

from backend.app.services.incident_service import create_incident
from backend.app.services.diagnosis_service import diagnose_incident
from backend.app.tools.account_tools import unlock_account
from backend.app.services.verification_service import verify_incident_resolution
from backend.app.services.resolution_service import resolve_incident


def run_account_recovery_agent(
    db: Session,
    customer_id: int,
    username: str,
    issue: str,
    authorized: bool = False,
) -> dict:
    """
    Run the complete account recovery workflow.

    Flow:
    Understand → Diagnose → Act → Verify → Resolve
    """

    # 1. Create incident
    incident = create_incident(
        db,
        customer_id=customer_id,
        issue=issue,
    )

    # 2. Diagnose
    diagnosis = diagnose_incident(
        db,
        incident.id,
    )

    if not diagnosis["success"]:
        return {
            "success": False,
            "stage": "diagnosis",
            "incident_id": incident.id,
            "message": diagnosis["message"],
        }

    account = diagnosis["account"]

    # 3. Decide whether an unlock action is required
    if not account["is_locked"]:
        return {
            "success": True,
            "stage": "diagnosis",
            "incident_id": incident.id,
            "message": "Account is not locked. Further investigation is required.",
            "diagnosis": diagnosis["diagnosis"],
        }

    # 4. Authorization check
    if not authorized:
        return {
            "success": False,
            "stage": "authorization",
            "incident_id": incident.id,
            "message": "Account unlock requires authorization.",
            "diagnosis": diagnosis["diagnosis"],
        }

    # 5. Take corrective action
    action = unlock_account(
        db,
        username=username,
        incident_id=incident.id,
        authorized=True,
    )

    if not action["success"]:
        return {
            "success": False,
            "stage": "action",
            "incident_id": incident.id,
            "message": action["message"],
        }

    # 6. Verify the fix
    verification = verify_incident_resolution(
        db,
        incident.id,
    )

    if not verification["verified"]:
        return {
            "success": False,
            "stage": "verification",
            "incident_id": incident.id,
            "message": verification["message"],
        }

    # 7. Resolve incident
    resolution = resolve_incident(
        db,
        incident.id,
    )

    return {
        "success": resolution["success"],
        "stage": "resolved",
        "incident_id": incident.id,
        "status": resolution["status"],
        "diagnosis": diagnosis["diagnosis"],
        "action": action["message"],
        "verification": verification["message"],
        "resolution": resolution["message"],
    }
