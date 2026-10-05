from sqlalchemy.orm import Session

from backend.app.models.database import Incident
from backend.app.tools.account_tools import get_customer_account


def verify_incident_resolution(
    db: Session,
    incident_id: int,
) -> dict:
    """
    Verify that the action actually resolved the incident.
    """

    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )

    if not incident:
        return {
            "success": False,
            "verified": False,
            "message": "Incident not found.",
        }

    customer = incident.customer

    if not customer or not customer.accounts:
        return {
            "success": False,
            "verified": False,
            "message": "Customer account not found.",
        }

    account = customer.accounts[0]

    account_data = get_customer_account(
        db,
        account.username,
    )

    if not account_data["found"]:
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
