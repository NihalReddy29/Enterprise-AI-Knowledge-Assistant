"""LLM provider abstraction supporting OpenAI, Gemini, Claude, and Fake."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class LLMResponse:
    """Normalized LLM completion response."""

    content: str
    provider: str
    model: str
    usage: dict | None = None


class LLMProvider(ABC):
    """Interface for chat completion backends."""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Generate a completion from system + user prompts."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier."""


class FakeLLMProvider(LLMProvider):
    """Deterministic local LLM for tests and offline development."""

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "fake-rag-v1"

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        context = _extract_section(user_prompt, "Context:")
        question = _extract_section(user_prompt, "Question:")

        if not context.strip() or context.strip().lower() in ("(no relevant context found)", ""):
            answer = "I don't have enough information."
        else:
            # Use the most relevant first context block as the grounded answer
            first_block = context.split("\n\n")[0].strip()
            # Strip citation header like [1] document.pdf (Page 12)
            lines = first_block.split("\n", 1)
            body = lines[1].strip() if len(lines) > 1 else first_block
            if not body:
                body = first_block
            answer = body

        return LLMResponse(
            content=answer,
            provider=self.provider_name,
            model=self.model_name,
        )


class OpenAILLMProvider(LLMProvider):
    """OpenAI / OpenAI-compatible chat completions."""

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI LLM")

        from openai import OpenAI

        kwargs: dict = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        self.client = OpenAI(**kwargs)
        self.model = settings.openai_llm_model

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self.model

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or ""
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        return LLMResponse(
            content=content.strip(),
            provider=self.provider_name,
            model=self.model,
            usage=usage,
        )


class GeminiLLMProvider(LLMProvider):
    """Google Gemini chat completions."""

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini LLM")

        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        self.model = settings.gemini_llm_model
        self._client = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=None,
        )
        self._genai = genai

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self.model

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        model = self._genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
        )
        response = model.generate_content(
            user_prompt,
            generation_config={
                "temperature": settings.llm_temperature,
                "max_output_tokens": settings.llm_max_tokens,
            },
        )
        content = (response.text or "").strip()
        return LLMResponse(
            content=content,
            provider=self.provider_name,
            model=self.model,
        )


class ClaudeLLMProvider(LLMProvider):
    """Anthropic Claude chat completions."""

    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Claude LLM")

        import anthropic

        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_llm_model

    @property
    def provider_name(self) -> str:
        return "claude"

    @property
    def model_name(self) -> str:
        return self.model

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        parts = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        content = "\n".join(parts).strip()
        usage = {
            "input_tokens": getattr(response.usage, "input_tokens", None),
            "output_tokens": getattr(response.usage, "output_tokens", None),
        }
        return LLMResponse(
            content=content,
            provider=self.provider_name,
            model=self.model,
            usage=usage,
        )


class LLMService:
    """High-level LLM service used by the RAG pipeline."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or create_llm_provider()

    @property
    def provider_name(self) -> str:
        return self.provider.provider_name

    @property
    def model_name(self) -> str:
        return self.provider.model_name

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        return self.provider.generate(system_prompt, user_prompt)


def create_llm_provider(provider_name: str | None = None) -> LLMProvider:
    """Factory for configured LLM provider."""
    name = (provider_name or settings.default_llm_provider).lower()

    if name == "fake":
        return FakeLLMProvider()
    if name in ("openai", "gpt", "llama", "openai_compatible"):
        return OpenAILLMProvider()
    if name == "gemini":
        return GeminiLLMProvider()
    if name in ("claude", "anthropic"):
        return ClaudeLLMProvider()

    raise ValueError(
        f"Unknown LLM provider '{name}'. Supported: openai, gemini, claude, fake"
    )


def get_llm_service() -> LLMService:
    """Return configured LLM service."""
    return LLMService()


def _extract_section(prompt: str, marker: str) -> str:
    if marker not in prompt:
        return ""
    after = prompt.split(marker, 1)[1]
    # Stop at next known section marker if present
    for next_marker in ("Question:", "Context:", "Chat History:"):
        if next_marker != marker and next_marker in after:
            after = after.split(next_marker, 1)[0]
            break
    return after.strip()
