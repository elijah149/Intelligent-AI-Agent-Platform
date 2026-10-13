from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.auth.rbac import require_permission
from backend.app.core.dependencies import get_db
from backend.app.models.database import User
from backend.app.services.incident_service import (
    create_incident,
    get_incident,
)


router = APIRouter(
    prefix="/incidents",
    tags=["Incidents"],
)


class IncidentCreateRequest(BaseModel):
    customer_id: int
    issue: str


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
async def create_new_incident(
    request: IncidentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission("incident.create")
    ),
):
    try:
        incident = create_incident(
            db=db,
            customer_id=request.customer_id,
            issue=request.issue,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return {
        "id": incident.id,
        "customer_id": incident.customer_id,
        "issue": incident.issue,
        "diagnosis": incident.diagnosis,
        "status": incident.status,
        "created_at": incident.created_at,
    }


@router.get("/{incident_id}")
async def get_incident_by_id(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission("incident.view")
    ),
):
    incident = get_incident(
        db=db,
        incident_id=incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found.",
        )

    return {
        "id": incident.id,
        "customer_id": incident.customer_id,
        "issue": incident.issue,
        "diagnosis": incident.diagnosis,
        "status": incident.status,
        "created_at": incident.created_at,
    }
