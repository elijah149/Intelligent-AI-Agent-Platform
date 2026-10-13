from collections.abc import Iterable

from sqlalchemy.orm import Session

from backend.app.agents.authorization import authorization_policy
from backend.app.services.incident_service import create_incident
from backend.app.services.diagnosis_service import diagnose_incident
from backend.app.services.verification_service import verify_incident_resolution
from backend.app.services.resolution_service import resolve_incident
from backend.app.tools.account_tools import unlock_account


def run_account_recovery_agent(
    db: Session,
    customer_id: int,
    username: str,
    issue: str,
    authorized: bool = False,
    permissions: Iterable[str] | None = None,
    performed_by: str | None = None,
) -> dict:
    """Recover a locked account using explicit server-side permissions."""
    granted_permissions = set(permissions or ())

    if not authorization_policy.can_execute(
        "create_incident", permissions=granted_permissions
    ):
        return {
            "success": False,
            "stage": "authorization",
            "message": "Incident creation requires permission.",
        }

    incident = create_incident(
        db, customer_id=customer_id, issue=issue
    )

    if not authorization_policy.can_execute(
        "diagnose_incident", permissions=granted_permissions
    ):
        return {
            "success": False,
            "stage": "authorization",
            "incident_id": incident.id,
            "message": "Incident diagnosis requires permission.",
        }

    diagnosis = diagnose_incident(
        db, incident.id, username=username
    )

    if not diagnosis.get("success"):
        return {
            "success": False,
            "stage": "diagnosis",
            "incident_id": incident.id,
            "message": diagnosis.get(
                "message", "Diagnosis failed."
            ),
        }

    account = diagnosis.get("account") or {}

    if not account.get("is_locked"):
        return {
            "success": True,
            "stage": "diagnosis",
            "incident_id": incident.id,
            "message": (
                "Account is not locked. Further investigation is required."
            ),
            "diagnosis": diagnosis.get("diagnosis"),
        }

    # Check every required permission before making any account changes.
    required_tools = (
        ("unlock_account", "Account unlock"),
        ("verify_incident_resolution", "Incident verification"),
        ("resolve_incident", "Incident resolution"),
    )

    for tool_name, action_name in required_tools:
        if not authorization_policy.can_execute(
            tool_name, permissions=granted_permissions
        ):
            return {
                "success": False,
                "stage": "authorization",
                "incident_id": incident.id,
                "message": (
                    f"{action_name} requires the appropriate permission."
                ),
                "diagnosis": diagnosis.get("diagnosis"),
            }

    # Permissions grant capability; explicit approval grants consent
    # for this particular recovery action.
    if not authorized:
        return {
            "success": True,
            "stage": "authorization",
            "status": "awaiting_authorization",
            "incident_id": incident.id,
            "message": (
                "Diagnosis confirmed that the account is locked. "
                "Explicit approval is required before unlocking it. "
                "No account changes were made."
            ),
            "diagnosis": diagnosis.get("diagnosis"),
        }

    unlock_result = unlock_account(
        db=db,
        username=username,
        incident_id=incident.id,
        authorized=True,
        performed_by=performed_by,
    )

    if not unlock_result.get("success"):
        return {
            "success": False,
            "stage": "unlock",
            "incident_id": incident.id,
            "message": unlock_result.get(
                "message", "Account unlock failed."
            ),
            "diagnosis": diagnosis.get("diagnosis"),
        }

    verification = verify_incident_resolution(
        db=db,
        incident_id=incident.id,
        username=username,
    )

    if not verification.get("success") or not verification.get("verified"):
        return {
            "success": False,
            "stage": "verification",
            "incident_id": incident.id,
            "message": verification.get(
                "message", "Account recovery could not be verified."
            ),
            "diagnosis": diagnosis.get("diagnosis"),
        }

    resolution = resolve_incident(
        db=db,
        incident_id=incident.id,
        username=username,
    )

    if not resolution.get("success"):
        return {
            "success": False,
            "stage": "resolution",
            "incident_id": incident.id,
            "message": resolution.get(
                "message", "Incident resolution failed."
            ),
            "diagnosis": diagnosis.get("diagnosis"),
        }

    return {
        "success": True,
        "stage": "resolved",
        "status": "resolved",
        "incident_id": incident.id,
        "message": resolution.get(
            "message", "Account recovery completed successfully."
        ),
        "diagnosis": diagnosis.get("diagnosis"),
    }
