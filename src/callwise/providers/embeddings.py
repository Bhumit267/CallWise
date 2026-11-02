"""Local sentence-transformers embedding provider implementation."""

from typing import List, Optional
from sentence_transformers import SentenceTransformer

from callwise.config import settings
from callwise.providers import EmbeddingProvider


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local embedding generator using HuggingFace sentence-transformers."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.embedding_model_name
        self._model: Optional[SentenceTransformer] = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the sentence transformer model on first use."""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_text(self, text: str) -> List[float]:
        """Generate a single normalized embedding vector for the text."""
        cleaned = text.strip()
        if not cleaned:
            return [0.0] * settings.embedding_dimension
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
