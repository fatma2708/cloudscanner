"""LLM router: pick the configured provider, or return None for the heuristic fallback."""

from __future__ import annotations

from app.core.config import Settings
from app.services.llm.base import LLMProvider


def get_provider(settings: Settings | None = None) -> LLMProvider | None:
    """Return the first configured LLM provider according to ``LLM_PROVIDER``.

    ``auto`` (default) prefers HuggingFace, then OpenAI, then Anthropic, then
    Gemini.  Returns ``None`` when no API keys are configured — callers then
    use the deterministic narrative engine.
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
        return None

    for name, cls, available in candidates:
        if name == requested:
            return cls(settings) if available else None
    return None
