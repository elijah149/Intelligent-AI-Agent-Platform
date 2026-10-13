from sqlalchemy.orm import Session

from backend.app.models.database import Account, Incident
from backend.app.tools.account_tools import get_customer_account


def verify_incident_resolution(
    db: Session,
    incident_id: int,
    username: str,
) -> dict:
    """Verify that the specific account linked to an incident is fixed."""

    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )

    if incident is None:
        return {
            "success": False,
            "verified": False,
            "message": "Incident not found.",
        }

    account = (
        db.query(Account)
        .filter(
            Account.username == username,
            Account.customer_id == incident.customer_id,
        )
        .first()
    )

    if account is None:
        return {
            "success": False,
            "verified": False,
            "message": (
                "The specified account does not belong "
                "to the customer associated with this incident."
            ),
        }

    account_data = get_customer_account(db, username)

    if not account_data.get("found"):
        return {
            "success": False,
            "verified": False,
            "message": "Unable to retrieve account.",
        }

    account_info = account_data["account"]

    is_resolved = (
        account_info["is_locked"] is False
        and account_info["status"] == "active"
        and account_info["failed_login_attempts"] == 0
    )

    if is_resolved:
        return {
            "success": True,
            "verified": True,
            "message": "Account unlock successfully verified.",
            "account": account_info,
        }

    return {
        "success": True,
        "verified": False,
        "message": "Account is still not in the expected state.",
        "account": account_info,
    }
