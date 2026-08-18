"""Concrete LLM providers: OpenAI, Anthropic, Google Gemini, HuggingFace.

Each provider talks to its vendor's chat-completions API over httpx. Keys are
read from settings; nothing is logged or persisted.
"""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.services.llm.base import LLMProvider


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.base_url = settings.openai_base_url.rstrip("/")

    async def complete(self, system: str, user: str, temperature: float = 0.4) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.anthropic_api_key
        self.model = settings.anthropic_model

    async def complete(self, system: str, user: str, temperature: float = 0.4) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": 2000,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model

    async def complete(self, system: str, user: str, temperature: float = 0.4) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": temperature},
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


class HuggingFaceProvider(LLMProvider):
    """HuggingFace Inference Providers - OpenAI-compatible chat endpoint.

    Talks to the HF router (router.huggingface.co/v1) which proxies to the
    configured model (e.g. Qwen3-Coder). The request format is identical to
    the OpenAI chat-completions API.
    """

    name = "huggingface"

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.hf_api_key
        self.model = settings.hf_model
        self.base_url = settings.hf_base_url.rstrip("/")

    async def complete(self, system: str, user: str, temperature: float = 0.4) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
