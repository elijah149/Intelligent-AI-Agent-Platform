from sqlalchemy.orm import Session

from backend.app.models.database import Account, Incident, LoginAuditLog
from backend.app.tools.account_tools import get_customer_account
from backend.app.services.incident_service import update_diagnosis


def diagnose_incident(
    db: Session,
    incident_id: int,
    username: str,
) -> dict:
    """
    Diagnose an incident using the specified customer's account.
    The account must belong to the customer associated with the incident.
    """

    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )

    if incident is None:
        return {
            "success": False,
            "message": "Incident not found.",
        }

    if incident.customer is None:
        return {
            "success": False,
            "message": "Customer associated with incident was not found.",
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
            "message": (
                "The specified account does not belong to "
                "the customer associated with this incident."
            ),
        }

    account_data = get_customer_account(db, username)

    if not account_data.get("found"):
        return {
            "success": False,
            "message": "Unable to retrieve account information.",
        }

    account_info = account_data["account"]

    # Read recent login audit events; this does not modify the account.
    audit_logs = (
        db.query(LoginAuditLog)
        .filter(LoginAuditLog.username == username)
        .order_by(LoginAuditLog.created_at.desc(), LoginAuditLog.id.desc())
        .limit(5)
        .all()
    )

    audit_evidence = [
        (
            f"audit id={log.id}, event={log.event}, "
            f"success={log.success}, created_at={log.created_at}"
        )
        for log in audit_logs
    ]

    if not audit_evidence:
        audit_evidence = ["No login audit events found for this username."]

    # Diagnosis: account is locked.
    if account_info["is_locked"]:
        root_cause = "Account is locked."

        evidence = [
            f"is_locked = {account_info['is_locked']}",
            f"failed_login_attempts = {account_info['failed_login_attempts']}",
            f"status = {account_info['status']}",
        ]

        evidence.extend(audit_evidence)
        confidence = 0.98
        recommended_action = "unlock_account"

        diagnosis_text = (
            f"Account '{account_info['username']}' is locked. "
            f"The account has {account_info['failed_login_attempts']} "
            "failed login attempts. The customer cannot log in "
            "because the account is currently locked."
        )

    # Diagnosis: account is not active.
    elif account_info["status"] != "active":
        root_cause = f"Account status is '{account_info['status']}'."

        evidence = [
            f"is_locked = {account_info['is_locked']}",
            f"status = {account_info['status']}",
            f"failed_login_attempts = {account_info['failed_login_attempts']}",
        ]

        evidence.extend(audit_evidence)
        confidence = 0.90
        recommended_action = "further_investigation"

        diagnosis_text = (
            f"Account '{account_info['username']}' is not active. "
            f"Current account status: {account_info['status']}."
        )

    # Diagnosis: account is active and unlocked.
    else:
        root_cause = "No account-level cause was identified."

        evidence = [
            f"is_locked = {account_info['is_locked']}",
            f"status = {account_info['status']}",
            f"failed_login_attempts = {account_info['failed_login_attempts']}",
        ]

        evidence.extend(audit_evidence)
        confidence = 0.70
        recommended_action = "further_investigation"

        diagnosis_text = (
            f"Account '{account_info['username']}' is active "
            "and not locked. The reported login problem requires "
            "further investigation."
        )

    # Include the account and audit evidence in the saved diagnosis.
    audit_summary = "\\n".join(f"- {item}" for item in audit_evidence)
    evidence_summary = (
        f"{diagnosis_text}\\n\\n"
        f"Evidence:\\n"
        f"- Account status: {account_info['status']}\\n"
        f"- Account locked: {account_info['is_locked']}\\n"
        f"- Failed login attempts: {account_info['failed_login_attempts']}\\n"
        f"Recent login audit events:\\n{audit_summary}\\n\\n"
        "Recommended next step: investigate the recorded login events and "
        "authentication service logs. No account changes were made."
    )

    incident = update_diagnosis(
        db=db,
        incident_id=incident_id,
        diagnosis=evidence_summary,
    )

    return {
        "success": True,
        "incident_id": incident.id,
        "status": incident.status,
        "problem": incident.issue,
        "root_cause": root_cause,
        "evidence": evidence,
        "confidence": confidence,
        "recommended_action": recommended_action,
        "diagnosis": incident.diagnosis,
        "account": account_info,
    }
