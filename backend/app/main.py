from fastapi import FastAPI

from backend.app.api.ai import router as ai_router


app = FastAPI(
    title="Intelligent AI Agent Platform",
    description=(
        "AI-powered customer support, problem diagnosis, "
        "resolution and multi-system integration platform."
    ),
    version="0.1.0",
)


app.include_router(ai_router)


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
        "status": "healthy"
    }
