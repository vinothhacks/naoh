"""Anthropic Claude adapter (Messages API)."""

from __future__ import annotations

import contextlib

import httpx

from book_to_skill.providers.base import LLMProvider, ProviderError, post_with_retries

# Verified against https://platform.claude.com/docs/en/api/overview (anthropic-version 2023-06-01).
DEFAULT_ENDPOINT = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    """POST /v1/messages with x-api-key + anthropic-version headers."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        endpoint: str = DEFAULT_ENDPOINT,
        version: str = ANTHROPIC_VERSION,
        client: httpx.Client | None = None,
        timeout: float = 120.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for Anthropic")
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.version = version
        self.name = "anthropic"
        self._client = client
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.version,
            "content-type": "application/json",
        }

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        owns_client = self._client is None
        client = self._client or httpx.Client()
        try:
            resp = post_with_retries(
                client, self.endpoint, headers=self._headers(), json=payload, timeout=self.timeout
            )
        finally:
            if owns_client:
                with contextlib.suppress(Exception):
                    client.close()
        data = resp.json()
        try:
            blocks = data["content"]
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise ProviderError(f"unexpected Anthropic response shape: {data}") from exc
