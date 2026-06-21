"""One OpenAI-compatible adapter.

Drives OpenAI, OpenRouter, Groq, Grok (xAI), DeepSeek, Qwen/DashScope, Ollama, and
any generic local endpoint -- switched purely by ``base_url``.
"""

from __future__ import annotations

import contextlib

import httpx

from book_to_skill.providers.base import LLMProvider, ProviderError, post_with_retries


class OpenAICompatibleProvider(LLMProvider):
    """Talks to any ``{base_url}/chat/completions`` endpoint with OpenAI's schema."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        name: str = "openai-compatible",
        extra_headers: dict[str, str] | None = None,
        client: httpx.Client | None = None,
        timeout: float = 120.0,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required for an OpenAI-compatible provider")
        if not model:
            raise ValueError("model is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.name = name
        self.extra_headers = dict(extra_headers or {})
        self._client = client
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        headers.update(self.extra_headers)
        return headers

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        owns_client = self._client is None
        client = self._client or httpx.Client()
        try:
            resp = post_with_retries(
                client, url, headers=self._headers(), json=payload, timeout=self.timeout
            )
        finally:
            if owns_client:
                with contextlib.suppress(Exception):
                    client.close()
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"unexpected response shape from {self.name}: {data}") from exc
