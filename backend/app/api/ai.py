from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.services.llm_service import get_llm_provider


router = APIRouter(
    prefix="/ai",
    tags=["AI"],
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):

    llm = get_llm_provider()

    prompt = f"""
You are an intelligent customer support AI agent.

Your job is to understand the customer's problem clearly
and provide a useful response.

Customer message:
{request.message}
"""

    response = await llm.generate(prompt)

    return ChatResponse(response=response)
