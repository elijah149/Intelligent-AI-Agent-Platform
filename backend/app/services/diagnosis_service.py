from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.models.database import Account, Incident, LoginAuditLog, User
from backend.app.services.incident_service import update_diagnosis


def diagnose_incident(
    db: Session,
    incident_id: int,
    username: str,
) -> dict:
    """Diagnose an incident from current account state and relevant evidence."""

    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )
    if incident is None:
        return {"success": False, "message": "Incident not found."}

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

    # User and Account are separate records; a matching User is optional.
    user = db.query(User).filter(User.username == username).first()
    now = datetime.now()
    user_locked = bool(
        user is not None
        and user.locked_until is not None
        and user.locked_until > now
    )
    user_inactive = user is not None and not user.is_active

    audit_logs = (
        db.query(LoginAuditLog)
        .filter(LoginAuditLog.username == username)
        .order_by(LoginAuditLog.created_at.desc(), LoginAuditLog.id.desc())
        .limit(5)
        .all()
    )

    evidence = [
        f"Account username: {account.username}",
        f"Current account status: {account.status}",
        f"Current account is_locked: {account.is_locked}",
        f"Current account failed_login_attempts: {account.failed_login_attempts}",
    ]

    if user is None:
        evidence.append(
            "No matching User record exists; User lock state could not be checked."
        )
    else:
        evidence.extend([
            f"User is_active: {user.is_active}",
            f"User locked_until: {user.locked_until}",
            f"User currently locked: {user_locked}",
            f"User failed_login_attempts: {user.failed_login_attempts}",
        ])

    if audit_logs:
        evidence.append("Recent historical login audit events:")
        for log in audit_logs:
            evidence.append(
                f"{log.created_at}: {log.event}, success={log.success}"
            )
    else:
        evidence.append("No login audit events found for this username.")

    # Current verified state takes priority over historical audit events.
    if user_locked:
        root_cause = "The matching User record is temporarily locked."
        confidence = 0.98
        recommended_action = "review_account_unlock"
        diagnosis_text = (
            f"User '{username}' is locked until {user.locked_until}. "
            "Review the lockout policy and authorize any unlock separately."
        )
    elif user_inactive:
        root_cause = "The matching User record is inactive."
        confidence = 0.95
        recommended_action = "review_user_status"
        diagnosis_text = (
            f"User '{username}' is inactive. Review the user status "
            "before taking corrective action."
        )
    elif account.is_locked:
        root_cause = "The customer account is currently locked."
        confidence = 0.98
        recommended_action = "unlock_account"
        diagnosis_text = (
            f"Account '{username}' is currently locked. "
            f"Recorded failed login attempts: {account.failed_login_attempts}."
        )
    elif account.status != "active":
        root_cause = f"Account status is '{account.status}'."
        confidence = 0.90
        recommended_action = "further_investigation"
        diagnosis_text = (
            f"Account '{username}' is not active. "
            f"Current status: {account.status}."
        )
    else:
        root_cause = "No current account-level cause was confirmed."
        confidence = 0.70
        recommended_action = "further_investigation"
        diagnosis_text = (
            f"Account '{username}' is currently active and not locked. "
            "Historical login failures, if present, do not prove a current "
            "lockout. Investigate authentication logs and the login flow."
        )

    full_diagnosis = (
        f"{diagnosis_text}\n\nEvidence:\n- "
        + "\n- ".join(evidence)
        + f"\n\nRecommended next step: {recommended_action}. "
        "No account or user state was changed by this diagnosis."
    )

    updated_incident = update_diagnosis(
        db=db,
        incident_id=incident_id,
        diagnosis=full_diagnosis,
    )

    return {
        "success": True,
        "incident_id": updated_incident.id,
        "status": updated_incident.status,
        "problem": updated_incident.issue,
        "root_cause": root_cause,
        "evidence": evidence,
        "confidence": confidence,
        "recommended_action": recommended_action,
        "diagnosis": updated_incident.diagnosis,
        "account": {
            "id": account.id,
            "username": account.username,
            "status": account.status,
            "failed_login_attempts": account.failed_login_attempts,
            "is_locked": account.is_locked,
        },
        "user_found": user is not None,
        "user_locked": user_locked,
        "user_active": user.is_active if user is not None else None,
    }
