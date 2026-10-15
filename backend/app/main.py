from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.ai import router as ai_router
from backend.app.api.agent import router as agent_router
from backend.app.api.auth import router as auth_router
from backend.app.api.incidents import router as incidents_router
from backend.app.api.integrations import router as integrations_router
from backend.app.api.knowledge import router as knowledge_router


app = FastAPI(
    title="Intelligent AI Agent Platform",
    description=(
        "AI-powered customer support, problem diagnosis, "
        "resolution and multi-system integration platform."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



app.include_router(
    ai_router,
)

app.include_router(
    agent_router,
)

app.include_router(
    auth_router,
)

app.include_router(
    incidents_router,
)


@app.get("/")
async def root():
    return {
        "name": "Intelligent AI Agent Platform",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
    }


app.include_router(knowledge_router)


app.include_router(integrations_router)
