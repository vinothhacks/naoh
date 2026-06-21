"""Provider presets, env loading, config.toml, pricing, and the provider factory."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from book_to_skill.providers import (
    AnthropicProvider,
    GeminiProvider,
    LLMProvider,
    OpenAICompatibleProvider,
    StubProvider,
)


@dataclass(frozen=True)
class ProviderPreset:
    kind: str  # "openai" | "anthropic" | "gemini" | "stub"
    base_url: str | None
    env_var: str | None
    default_model: str | None


# Base URLs / env vars verified against each provider's current docs (June 2026).
PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "openai": ProviderPreset(
        "openai", "https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-4o-mini"
    ),
    "openrouter": ProviderPreset(
        "openai", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "openai/gpt-4o-mini"
    ),
    "groq": ProviderPreset(
        "openai", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "openai/gpt-oss-20b"
    ),
    "grok": ProviderPreset("openai", "https://api.x.ai/v1", "XAI_API_KEY", "grok-2-latest"),
    "deepseek": ProviderPreset(
        "openai", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY", "deepseek-chat"
    ),
    "qwen": ProviderPreset(
        "openai",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "DASHSCOPE_API_KEY",
        "qwen-plus",
    ),
    "ollama": ProviderPreset("openai", "http://localhost:11434/v1", None, "llama3.2"),
    "local": ProviderPreset("openai", None, "LOCAL_API_KEY", None),
    "anthropic": ProviderPreset(
        "anthropic",
        "https://api.anthropic.com/v1/messages",
        "ANTHROPIC_API_KEY",
        "claude-sonnet-4-6",
    ),
    "gemini": ProviderPreset(
        "gemini",
        "https://generativelanguage.googleapis.com/v1beta",
        "GEMINI_API_KEY",
        "gemini-2.5-flash",
    ),
    "stub": ProviderPreset("stub", None, None, "stub-model"),
}

# USD per 1,000,000 tokens (input, output). These drift -- VERIFY before relying on cost output:
#   Claude:   https://docs.claude.com/en/docs/about-claude/pricing
#   OpenAI:   https://openai.com/api/pricing
#   Groq:     https://groq.com/pricing
#   others:   each provider's pricing page
MODEL_PRICES: dict[str, dict[str, float]] = {
    "claude-fable-5": {"input": 10.0, "output": 50.0},
    "claude-opus-4-8": {"input": 5.0, "output": 25.0},
    "claude-opus-4-7": {"input": 5.0, "output": 25.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "openai/gpt-oss-20b": {"input": 0.10, "output": 0.50},
    "deepseek-chat": {"input": 0.27, "output": 1.10},
    "stub-model": {"input": 0.0, "output": 0.0},
}


class ConfigError(RuntimeError):
    """Raised for invalid provider configuration (missing key, unknown provider, ...)."""


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load an optional TOML config (path arg > BOOK_TO_SKILL_CONFIG env). Returns {} if none."""
    candidate = path or os.environ.get("BOOK_TO_SKILL_CONFIG")
    if not candidate:
        return {}
    p = Path(candidate)
    if not p.is_file():
        return {}
    with p.open("rb") as fh:
        return tomllib.load(fh)


def select_provider_name(cli_provider: str | None) -> str:
    """Precedence: --provider flag > BOOK_TO_SKILL_PROVIDER env > error."""
    name = cli_provider or os.environ.get("BOOK_TO_SKILL_PROVIDER")
    if not name:
        raise ConfigError(
            "No provider selected. Pass --provider <name> or set BOOK_TO_SKILL_PROVIDER. "
            f"Choices: {', '.join(sorted(PROVIDER_PRESETS))}."
        )
    name = name.strip().lower()
    if name not in PROVIDER_PRESETS:
        raise ConfigError(
            f"Unknown provider {name!r}. Choices: {', '.join(sorted(PROVIDER_PRESETS))}."
        )
    return name


def default_model_for(name: str) -> str | None:
    preset = PROVIDER_PRESETS.get(name)
    return preset.default_model if preset else None


def build_provider(
    name: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    client: Any = None,
) -> LLMProvider:
    """Construct a provider from a preset, resolving model/base_url/api_key (arg > env > preset)."""
    if name not in PROVIDER_PRESETS:
        raise ConfigError(f"Unknown provider {name!r}.")
    preset = PROVIDER_PRESETS[name]

    resolved_model = model or preset.default_model
    resolved_base = base_url or preset.base_url
    resolved_key = api_key or (os.environ.get(preset.env_var) if preset.env_var else None)

    if preset.kind == "stub":
        return StubProvider(model=resolved_model or "stub-model")

    if preset.kind == "anthropic":
        if not resolved_key:
            raise ConfigError(f"{name}: set {preset.env_var} or pass --api-key.")
        return AnthropicProvider(api_key=resolved_key, model=resolved_model, client=client)

    if preset.kind == "gemini":
        if not resolved_key:
            raise ConfigError(f"{name}: set {preset.env_var} or pass --api-key.")
        return GeminiProvider(
            api_key=resolved_key, model=resolved_model, base_url=resolved_base, client=client
        )

    # OpenAI-compatible family.
    if not resolved_base:
        raise ConfigError(f"{name}: a base_url is required (pass --base-url).")
    if not resolved_model:
        raise ConfigError(f"{name}: a model is required (pass --model).")
    if name == "ollama" and not resolved_key:
        resolved_key = "ollama"  # placeholder; Ollama ignores the key
    if preset.env_var and not resolved_key and name != "local":
        raise ConfigError(f"{name}: set {preset.env_var} or pass --api-key.")
    return OpenAICompatibleProvider(
        base_url=resolved_base,
        api_key=resolved_key,
        model=resolved_model,
        name=name,
        client=client,
    )


def estimate_cost(model: str | None, input_tokens: int, output_tokens: int) -> float | None:
    """Estimate USD cost; None if the model is not in MODEL_PRICES (prices drift -- verify)."""
    if not model or model not in MODEL_PRICES:
        return None
    price = MODEL_PRICES[model]
    return round(
        (input_tokens / 1_000_000) * price["input"] + (output_tokens / 1_000_000) * price["output"],
        4,
    )
