"""Provider ABC + a shared HTTP helper with bounded exponential-backoff retries."""

from __future__ import annotations

import abc
import time
from contextlib import suppress

import httpx

# Transient statuses worth retrying.
RETRY_STATUS = {429, 500, 502, 503, 504}
DEFAULT_TIMEOUT_S = 120.0


class ProviderError(RuntimeError):
    """Raised on a non-retryable HTTP error or after retries are exhausted."""


def _sleep(seconds: float) -> None:
    # Indirection so tests can monkeypatch sleep without real delays.
    time.sleep(seconds)


class LLMProvider(abc.ABC):
    """Abstract chat-completion provider."""

    name: str = "provider"

    @abc.abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        """Return the assistant text for a single system+user turn."""
        raise NotImplementedError


def post_with_retries(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str],
    json: dict,
    timeout: float = DEFAULT_TIMEOUT_S,
    max_retries: int = 4,
    backoff_base: float = 0.5,
) -> httpx.Response:
    """POST JSON with retries on 429/5xx and transport errors.

    Never logs headers or bodies (they may carry API keys).
    """
    last_text = ""
    for attempt in range(max_retries + 1):
        try:
            resp = client.post(url, headers=headers, json=json, timeout=timeout)
        except httpx.RequestError as exc:
            if attempt >= max_retries:
                raise ProviderError(f"request to {url} failed: {exc!r}") from exc
            _sleep(backoff_base * (2**attempt))
            continue

        if resp.status_code in RETRY_STATUS and attempt < max_retries:
            delay = backoff_base * (2**attempt)
            retry_after = resp.headers.get("retry-after")
            if retry_after:
                with suppress(ValueError):
                    delay = max(delay, float(retry_after))
            _sleep(delay)
            last_text = resp.text[:300]
            continue

        if resp.status_code >= 400:
            raise ProviderError(f"HTTP {resp.status_code} from {url}: {resp.text[:300]}")
        return resp

    raise ProviderError(f"exhausted retries for {url}: {last_text}")
