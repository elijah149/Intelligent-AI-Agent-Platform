from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.models.database import IncidentApproval


def create_unlock_approval(
    db: Session,
    incident_id: int,
    username: str,
    requested_by: str,
) -> IncidentApproval:
    """
    Create a pending approval for a specific account-unlock action.
    """

    approval = IncidentApproval(
        incident_id=incident_id,
        action="unlock_account",
        target_username=username,
        requested_by=requested_by,
        status="pending",
    )

    db.add(approval)
    db.commit()
    db.refresh(approval)

    return approval


def get_approval(
    db: Session,
    approval_id: int,
) -> IncidentApproval | None:
    return (
        db.query(IncidentApproval)
        .filter(IncidentApproval.id == approval_id)
        .first()
    )


def approve_approval(
    db: Session,
    approval_id: int,
    approved_by: str,
) -> IncidentApproval:
    """
    Approve a pending approval.

    This function only changes the approval record.
    It does NOT execute the account action.
    """

    approval = get_approval(db, approval_id)

    if approval is None:
        raise ValueError("Approval not found.")

    if approval.status != "pending":
        raise ValueError(
            f"Approval cannot be approved because its status is "
            f"'{approval.status}'."
        )

    approval.status = "approved"
    approval.approved_by = approved_by
    approval.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)

    db.commit()
    db.refresh(approval)

    return approval


def consume_approval(
    db: Session,
    approval_id: int,
    incident_id: int,
    username: str,
) -> IncidentApproval:
    """
    Consume an approved unlock authorization.

    The approval must match the exact incident and target account.
    """

    approval = get_approval(db, approval_id)

    if approval is None:
        raise ValueError("Approval not found.")

    if approval.status != "approved":
        raise ValueError(
            "Approval is not approved."
        )

    if approval.action != "unlock_account":
        raise ValueError(
            "Approval is not valid for account unlocking."
        )

    if approval.incident_id != incident_id:
        raise ValueError(
            "Approval does not belong to this incident."
        )

    if approval.target_username != username:
        raise ValueError(
            "Approval does not belong to this account."
        )

    if approval.consumed_at is not None:
        raise ValueError(
            "Approval has already been consumed."
        )

    approval.status = "consumed"
    approval.consumed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    db.commit()
    db.refresh(approval)

    return approval
