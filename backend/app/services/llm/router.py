"""LLM router: pick the configured provider and raise if none is available."""

from __future__ import annotations

from app.core.config import Settings
from app.services.llm.base import LLMProvider


class LLMConfigError(Exception):
    """Raised when no LLM provider is configured."""


def get_provider(settings: Settings | None = None) -> LLMProvider:
    """Return the configured LLM provider.

    ``auto`` (default) prefers HuggingFace, then OpenAI, then Anthropic, then
    Gemini.  Raises :class:`LLMConfigError` when no API key is configured.
    """
    from app.services.llm.providers import (
        AnthropicProvider,
        GeminiProvider,
        HuggingFaceProvider,
        OpenAIProvider,
    )

    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()

    requested = settings.llm_provider.lower()
    candidates: list[tuple[str, type[LLMProvider], bool]] = [
        ("huggingface", HuggingFaceProvider, settings.has_hf),
        ("openai", OpenAIProvider, settings.has_openai),
        ("anthropic", AnthropicProvider, settings.has_anthropic),
        ("gemini", GeminiProvider, settings.has_gemini),
    ]

    if requested == "auto":
        for _, cls, available in candidates:
            if available:
                return cls(settings)
        raise LLMConfigError(
            "No LLM provider configured. Set at least one API key "
            "(HF_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, or GEMINI_API_KEY)."
        )

    for name, cls, available in candidates:
        if name == requested:
            if not available:
                raise LLMConfigError(
                    f"LLM provider '{name}' is configured but its API key is missing."
                )
            return cls(settings)

    raise LLMConfigError(f"Unknown LLM provider: '{requested}'.")
