"""Provider interfaces for interchangeable LLM, TTS, and Embedding engines."""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, List


class LLMProvider(ABC):
    """Abstract interface for text generation and agent LLMs."""

    @abstractmethod
    async def generate_response(self, prompt: str, system_prompt: str = "") -> str:
        """Generate a complete text completion."""
        pass


class TTSProvider(ABC):
    """Abstract interface for text-to-speech synthesis."""

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Synthesize text into raw audio bytes."""
        pass


class EmbeddingProvider(ABC):
    """Abstract interface for generating vector embeddings."""

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Convert a single text into an embedding vector."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Convert a batch of texts into embedding vectors."""
        pass
