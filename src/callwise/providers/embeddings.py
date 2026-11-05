"""Local sentence-transformers embedding provider implementation."""

import hashlib
import logging
import math
from typing import Any, List, Optional

from callwise.config import settings
from callwise.providers import EmbeddingProvider

logger = logging.getLogger(__name__)


def _deterministic_embedding(text: str, dim: int = 384) -> List[float]:
    """Generate a deterministic normalized embedding vector when deep learning backend is unavailable."""
    words = text.lower().split()
    if not words:
        return [0.0] * dim
    vec = [0.0] * dim
    for word in words:
        h = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
        for i in range(dim):
            val = ((h >> (i % 64)) & 0xFF) / 128.0 - 1.0
            vec[i] += val
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        return [x / norm for x in vec]
    return [0.0] * dim


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local embedding generator using HuggingFace sentence-transformers with resilient fallback."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.embedding_model_name
        self._model: Optional[Any] = None

    @property
    def model(self) -> Any:
        """Lazy load the sentence transformer model on first use."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name, local_files_only=True)
            except Exception as e:
                logger.warning(
                    "SentenceTransformer unavailable (%s). Falling back to deterministic embeddings.",
                    e,
                )
                self._model = "fallback"
        return self._model

    def embed_text(self, text: str) -> List[float]:
        """Generate a single normalized embedding vector for the text."""
        cleaned = text.strip()
        if not cleaned:
            return [0.0] * settings.embedding_dimension
        if self.model == "fallback":
            return _deterministic_embedding(cleaned, settings.embedding_dimension)

        embedding = self.model.encode(
            cleaned,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate normalized embedding vectors for a batch of texts."""
        if not texts:
            return []
        cleaned_texts = [t.strip() if t.strip() else " " for t in texts]
        if self.model == "fallback":
            return [
                _deterministic_embedding(t, settings.embedding_dimension)
                for t in cleaned_texts
            ]

        embeddings = self.model.encode(
            cleaned_texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32,
        )
        return embeddings.tolist()


_default_embedding_provider: Optional[EmbeddingProvider] = None


def get_embedding_provider() -> EmbeddingProvider:
    """Retrieve or initialize the active embedding provider."""
    global _default_embedding_provider
    if _default_embedding_provider is None:
        _default_embedding_provider = LocalEmbeddingProvider()
    return _default_embedding_provider
