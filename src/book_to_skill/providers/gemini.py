"""Google Gemini adapter (native generateContent endpoint).

Gemini also exposes an OpenAI-compatible endpoint
(``https://generativelanguage.googleapis.com/v1beta/openai/`` with a Bearer key),
which can be driven by ``OpenAICompatibleProvider``. This dedicated adapter uses the
native API and the ``x-goog-api-key`` header.
"""

from __future__ import annotations

import contextlib

import httpx

from book_to_skill.providers.base import LLMProvider, ProviderError, post_with_retries

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(LLMProvider):
    """POST {base_url}/models/{model}:generateContent with x-goog-api-key."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-2.5-flash",
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.Client | None = None,
        timeout: float = 120.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for Gemini")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.name = "gemini"
        self._client = client
        self.timeout = timeout

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        url = f"{self.base_url}/models/{self.model}:generateContent"
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        }
        owns_client = self._client is None
        client = self._client or httpx.Client()
        try:
            resp = post_with_retries(
                client, url, headers=headers, json=payload, timeout=self.timeout
            )
        finally:
            if owns_client:
                with contextlib.suppress(Exception):
                    client.close()
        data = resp.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"unexpected Gemini response shape: {data}") from exc
