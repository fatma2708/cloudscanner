"""Abstract LLM provider interface.

Every provider implements a single ``complete`` method plus a ``name`` so the
router can pick between them. Implementations use raw HTTP (httpx) to avoid
heavy SDK dependencies.
"""

from __future__ import annotations

import abc


class LLMProvider(abc.ABC):
    """Minimal chat-completion interface implemented by each vendor."""

    name: str = "base"

    @abc.abstractmethod
    async def complete(self, system: str, user: str, temperature: float = 0.4) -> str:
        """Return the model's text completion for the given messages."""

    async def close(self) -> None:
        """Release any resources (default no-op)."""
        return None
