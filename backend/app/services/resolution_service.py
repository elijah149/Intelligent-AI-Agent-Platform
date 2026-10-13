from sqlalchemy.orm import Session

from backend.app.services.incident_service import (
    close_incident,
    get_resolution_verification_token,
)
from backend.app.services.verification_service import (
    verify_incident_resolution,
)


def resolve_incident(
    db: Session,
    incident_id: int,
    username: str,
) -> dict:
    """Resolve an incident only after verifying its specific account."""

    verification = verify_incident_resolution(
        db=db,
        incident_id=incident_id,
        username=username,
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
        verification_token=get_resolution_verification_token(),
    )

    return {
        "success": True,
        "resolved": True,
        "incident_id": incident.id,
        "status": incident.status,
        "message": "Incident successfully resolved.",
        "account": verification["account"],
    }
