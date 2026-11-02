"""Application configuration loaded from environment variables."""

from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings for Callwise, populated from env vars and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5433/callwise",
        description="Async PostgreSQL connection URL",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5433/callwise",
        description="Sync PostgreSQL connection URL for migrations",
    )

    # LiveKit real-time audio pipeline
    livekit_url: str = Field(default="", description="LiveKit server WebSocket URL")
    livekit_api_key: str = Field(default="", description="LiveKit API Key")
    livekit_api_secret: str = Field(default="", description="LiveKit API Secret")

    # LLM Settings
    llm_provider: Literal["groq", "gemini", "ollama"] = Field(
        default="groq",
        description="LLM provider name: groq, gemini, or ollama",
    )
    groq_api_key: str = Field(default="", description="Groq API Key")
    groq_model: str = Field(
        default="qwen/qwen3.8-27b",
        description="Groq model ID (e.g. qwen/qwen3.8-27b, openai/gpt-oss-120b)",
    )

    gemini_api_key: str = Field(default="", description="Google Gemini API Key")
    gemini_model: str = Field(
        default="gemini-2.0-flash",
        description="Google Gemini model ID",
    )

    ollama_base_url: str = Field(
        default="http://localhost:11434/v1",
        description="Ollama OpenAI-compatible endpoint",
    )
    ollama_model: str = Field(
        default="llama3.2",
        description="Ollama model name",
    )

    # STT Settings
    stt_provider: str = Field(default="deepgram", description="STT Provider")
    deepgram_api_key: str = Field(default="", description="Deepgram API Key")

    # TTS Settings
    tts_provider: Literal["deepgram", "cartesia"] = Field(
        default="deepgram",
        description="TTS provider name: deepgram or cartesia",
    )
    cartesia_api_key: str = Field(default="", description="Cartesia API Key")
    cartesia_voice: str = Field(
        default="248be419-c632-4f23-adf1-5324ed7dbf1d",
        description="Cartesia voice ID",
    )
    deepgram_voice: str = Field(
        default="aura-asteria-en",
        description="Deepgram Aura voice ID",
    )

    # Embeddings
    embedding_provider: str = Field(
        default="local",
        description="Embedding provider identifier",
    )
    embedding_model_name: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence-transformer model name",
    )
    embedding_dimension: int = Field(
        default=384,
        description="Vector dimension for embeddings",
    )
    similarity_threshold: float = Field(
        default=0.45,
        description="Cosine similarity cutoff for knowledge retrieval",
    )


settings = Settings()
