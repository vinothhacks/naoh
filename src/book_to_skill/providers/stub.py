"""Hidden offline provider for CI / smoke tests: returns deterministic canned text."""

from __future__ import annotations

from book_to_skill.providers.base import LLMProvider


class StubProvider(LLMProvider):
    """Returns deterministic markdown without any network call."""

    def __init__(self, *, model: str = "stub-model", canned: str | None = None) -> None:
        self.model = model
        self.name = "stub"
        self._canned = canned

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        if self._canned is not None:
            return self._canned
        # Echo a compact, deterministic summary derived from the prompt.
        first_line = user.strip().splitlines()[0] if user.strip() else "section"
        snippet = " ".join(user.split())[:160]
        return (
            f"## Summary\n\n"
            f"{first_line}\n\n"
            f"Key points distilled by the stub provider: {snippet}\n\n"
            f"- point one\n- point two\n- point three\n"
        )
