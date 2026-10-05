from sqlalchemy.orm import Session

from backend.app.models.database import Incident
from backend.app.tools.account_tools import get_customer_account
from backend.app.services.incident_service import update_diagnosis


def diagnose_incident(
    db: Session,
    incident_id: int,
) -> dict:
    """
    Investigate an incident and generate a diagnosis
    based on the actual account state in the database.
    """

    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )

    if not incident:
        return {
            "success": False,
            "message": "Incident not found.",
        }

    customer = incident.customer

    if not customer or not customer.accounts:
        return {
            "success": False,
            "message": "No customer account was found.",
        }

    account = customer.accounts[0]

    account_data = get_customer_account(
        db,
        account.username,
    )

    if not account_data["found"]:
        return {
            "success": False,
            "message": "Unable to retrieve account information.",
        }

    account_info = account_data["account"]

    if account_info["is_locked"]:
        diagnosis = (
            f"Account '{account_info['username']}' is locked. "
            f"The account has {account_info['failed_login_attempts']} "
            f"failed login attempts. "
            "The customer cannot log in because the account is currently locked."
        )

    elif account_info["status"] != "active":
        diagnosis = (
            f"Account '{account_info['username']}' is not active. "
            f"Current account status: {account_info['status']}."
        )

    else:
        diagnosis = (
            f"Account '{account_info['username']}' is active and not locked. "
            "The reported login problem requires further investigation."
        )

    incident = update_diagnosis(
        db,
        incident_id,
        diagnosis,
    )

    return {
        "success": True,
        "incident_id": incident.id,
        "status": incident.status,
        "diagnosis": incident.diagnosis,
        "account": account_info,
    }
