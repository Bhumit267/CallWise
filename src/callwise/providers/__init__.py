"""Provider interfaces for interchangeable LLM, TTS, Embedding, Calendar, and Email engines."""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, List

from callwise.providers.calendar import (
    CalendarProvider,
    LocalCalendarProvider,
    TimeSlot,
    get_calendar_provider,
)
from callwise.providers.email import (
    ConsoleEmailProvider,
    EmailMessage,
    EmailProvider,
    SMTPEmailProvider,
    get_email_provider,
)


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


__all__ = [
    "LLMProvider",
    "TTSProvider",
    "EmbeddingProvider",
    "CalendarProvider",
    "LocalCalendarProvider",
    "TimeSlot",
    "get_calendar_provider",
    "EmailProvider",
    "ConsoleEmailProvider",
    "SMTPEmailProvider",
    "EmailMessage",
    "get_email_provider",
]
