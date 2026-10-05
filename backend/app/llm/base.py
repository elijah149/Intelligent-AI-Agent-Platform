from abc import ABC, abstractmethod


class LLMProvider(ABC):

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Generate a response from the language model."""
        raise NotImplementedError
