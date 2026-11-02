"""LLM Provider implementations for Groq, Gemini, and Ollama with 429 retry backoff."""

import logging
from typing import Any, Dict, List, Optional
import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from callwise.config import settings
from callwise.providers import LLMProvider

logger = logging.getLogger(__name__)


def is_rate_limit_error(exception: BaseException) -> bool:
    """Check if an exception is an HTTP 429 Rate Limit error."""
    # Check status code attribute on HTTP errors across client libraries
    status_code = getattr(exception, "status_code", None)
    if status_code == 429:
        return True
    # Check message contents
    msg = str(exception).lower()
    return "429" in msg or "rate limit" in msg or "quota" in msg or "too many requests" in msg


class GroqLLMProvider(LLMProvider):
    """Groq fast cloud inference provider (e.g. Llama 3.3 70B)."""

    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None):
        import groq
        self.model_name = model_name or settings.groq_model
        self.api_key = api_key or settings.groq_api_key
        self.client = groq.AsyncGroq(api_key=self.api_key)

    @retry(
        retry=retry_if_exception(is_rate_limit_error),
        wait=wait_random_exponential(multiplier=1.5, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def generate_response(self, prompt: str, system_prompt: str = "") -> str:
        """Generate response with retry on 429."""
        logger.info(f"[LLM: Groq] Calling model {self.model_name}")
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.3,
            max_tokens=600,
        )
        return response.choices[0].message.content or ""


class GeminiLLMProvider(LLMProvider):
    """Google Gemini Flash provider using official google-genai SDK."""

    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None):
        from google import genai
        self.model_name = model_name or settings.gemini_model
        self.api_key = api_key or settings.gemini_api_key
        self.client = genai.Client(api_key=self.api_key)

    @retry(
        retry=retry_if_exception(is_rate_limit_error),
        wait=wait_random_exponential(multiplier=1.5, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def generate_response(self, prompt: str, system_prompt: str = "") -> str:
        """Generate response with retry on 429."""
        logger.info(f"[LLM: Gemini] Calling model {self.model_name}")
        from google.genai import types

        config = types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=600,
        )
        if system_prompt:
            config.system_instruction = system_prompt

        # Run client call
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )
        return response.text or ""


class OllamaLLMProvider(LLMProvider):
    """Local Ollama provider via OpenAI-compatible endpoint."""

    def __init__(self, model_name: Optional[str] = None, base_url: Optional[str] = None):
        import openai
        self.model_name = model_name or settings.ollama_model
        self.base_url = base_url or settings.ollama_base_url
        self.client = openai.AsyncOpenAI(
            base_url=self.base_url,
            api_key="ollama",
        )

    @retry(
        retry=retry_if_exception(is_rate_limit_error),
        wait=wait_random_exponential(multiplier=1.5, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def generate_response(self, prompt: str, system_prompt: str = "") -> str:
        """Generate local response via Ollama endpoint."""
        logger.info(f"[LLM: Ollama] Calling model {self.model_name}")
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.3,
            max_tokens=600,
        )
        return response.choices[0].message.content or ""


def get_llm_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """Instantiate and return the configured LLMProvider."""
    name = (provider_name or settings.llm_provider).lower().strip()

    if name == "groq":
        return GroqLLMProvider()
    elif name == "gemini":
        return GeminiLLMProvider()
    elif name == "ollama":
        return OllamaLLMProvider()
    else:
        raise ValueError(
            f"Unsupported LLM provider '{name}'. Supported providers: groq, gemini, ollama."
        )
