from fastapi import APIRouter, Depends
from pydantic import BaseModel

from typing import Optional

from backend.app.agents.agent_loop import agent_loop
from backend.app.auth.rbac import get_user_permissions, require_permission
from backend.app.core.database import SessionLocal
from backend.app.models.database import User


router = APIRouter(
    prefix="/agent",
    tags=["Agent"],
)


class AgentRunRequest(BaseModel):
    customer_message: str
    username: str
    incident_id: Optional[int] = None


@router.post("/run")
async def run_agent(
    request: AgentRunRequest,
    current_user: User = Depends(
        require_permission("agent.run")
    ),
):

    db = SessionLocal()

    try:
        permissions = get_user_permissions(current_user)

        result = await agent_loop.run(
            db=db,
            customer_message=request.customer_message,
            username=request.username,
            incident_id=request.incident_id,
            permissions=permissions,
            actor_username=current_user.username,
        )

        return result

    finally:
        db.close()
