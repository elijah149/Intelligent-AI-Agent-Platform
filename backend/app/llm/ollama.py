import httpx

from backend.app.core.config import settings
from backend.app.llm.base import LLMProvider


class OllamaProvider(LLMProvider):

    async def generate(self, prompt: str) -> str:
        url = f"{settings.ollama_base_url}/api/generate"

        payload = {
            "model": settings.ollama_model,
            "prompt": prompt,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)

        response.raise_for_status()

        data = response.json()

        return data["response"]
