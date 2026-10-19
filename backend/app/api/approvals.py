from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.auth.rbac import require_permission
from backend.app.core.dependencies import get_db
from backend.app.models.database import User
from backend.app.services.approval_service import approve_approval


router = APIRouter(
    prefix="/approvals",
    tags=["Approvals"],
)


@router.post("/{approval_id}/approve")
async def approve_incident_action(
    approval_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission("incident.approve")
    ),
):
    """
    Approve a pending incident action.

    Approval is restricted to users with incident.approve permission.
    The approval itself does not execute the underlying action.
    """

    try:
        approval = approve_approval(
            db=db,
            approval_id=approval_id,
            approved_by=current_user.username,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "success": True,
        "approval": {
            "id": approval.id,
            "incident_id": approval.incident_id,
            "action": approval.action,
            "target_username": approval.target_username,
            "requested_by": approval.requested_by,
            "approved_by": approval.approved_by,
            "status": approval.status,
            "created_at": approval.created_at,
            "approved_at": approval.approved_at,
            "consumed_at": approval.consumed_at,
        },
    }
