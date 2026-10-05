from backend.app.core.config import settings
from backend.app.llm.ollama import OllamaProvider


def get_llm_provider():

    if settings.llm_provider == "ollama":
        return OllamaProvider()

    raise ValueError(
        f"Unsupported LLM provider: {settings.llm_provider}"
    )
