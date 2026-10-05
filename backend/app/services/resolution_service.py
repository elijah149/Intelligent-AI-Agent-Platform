from sqlalchemy.orm import Session

from backend.app.services.incident_service import close_incident
from backend.app.services.verification_service import verify_incident_resolution


def resolve_incident(
    db: Session,
    incident_id: int,
) -> dict:
    """
    Verify an incident and resolve it only when the
    underlying problem has actually been fixed.
    """

    verification = verify_incident_resolution(
        db,
        incident_id,
    )

    if not verification["success"]:
        return {
            "success": False,
            "resolved": False,
            "message": verification["message"],
        }

    if not verification["verified"]:
        return {
            "success": False,
            "resolved": False,
            "message": (
                "Incident cannot be resolved because "
                "the problem was not successfully fixed."
            ),
            "account": verification.get("account"),
        }

    incident = close_incident(
        db,
        incident_id,
    )

    return {
        "success": True,
        "resolved": True,
        "incident_id": incident.id,
        "status": incident.status,
        "message": "Incident successfully resolved.",
        "account": verification["account"],
    }
