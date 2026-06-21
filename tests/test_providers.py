"""Provider adapter tests: mocked HTTP only, never a real API call."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from book_to_skill import config
from book_to_skill.providers import base as base_mod
from book_to_skill.providers.anthropic import AnthropicProvider
from book_to_skill.providers.base import ProviderError
from book_to_skill.providers.gemini import GeminiProvider
from book_to_skill.providers.openai_compatible import OpenAICompatibleProvider
from book_to_skill.providers.stub import StubProvider


@respx.mock
def test_openai_compatible_request_and_parse():
    url = "https://api.groq.com/openai/v1/chat/completions"
    route = respx.post(url).mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})
    )
    provider = OpenAICompatibleProvider(
        base_url="https://api.groq.com/openai/v1",
        api_key="secret-key",
        model="openai/gpt-oss-20b",
        name="groq",
    )
    out = provider.complete("be terse", "summarize", max_tokens=42, temperature=0.1)
    assert out == "hello"

    req = route.calls.last.request
    assert req.headers["authorization"] == "Bearer secret-key"
    body = json.loads(req.content)
    assert body["model"] == "openai/gpt-oss-20b"
    assert body["max_tokens"] == 42
    assert body["messages"][0] == {"role": "system", "content": "be terse"}
    assert body["messages"][1] == {"role": "user", "content": "summarize"}


@respx.mock
def test_retry_on_429_then_success(monkeypatch):
    monkeypatch.setattr(base_mod, "_sleep", lambda _s: None)
    url = "https://api.openai.com/v1/chat/completions"
    route = respx.post(url).mock(
        side_effect=[
            httpx.Response(429, json={"error": "slow down"}),
            httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
        ]
    )
    provider = OpenAICompatibleProvider(
        base_url="https://api.openai.com/v1", api_key="k", model="gpt-4o-mini"
    )
    assert provider.complete("s", "u") == "ok"
    assert route.call_count == 2


@respx.mock
def test_openai_compatible_4xx_raises(monkeypatch):
    monkeypatch.setattr(base_mod, "_sleep", lambda _s: None)
    url = "https://api.openai.com/v1/chat/completions"
    respx.post(url).mock(return_value=httpx.Response(401, text="bad key"))
    provider = OpenAICompatibleProvider(
        base_url="https://api.openai.com/v1", api_key="k", model="gpt-4o-mini"
    )
    with pytest.raises(ProviderError):
        provider.complete("s", "u")


@respx.mock
def test_anthropic_headers_and_parse():
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200, json={"content": [{"type": "text", "text": "claude-says-hi"}]}
        )
    )
    provider = AnthropicProvider(api_key="ak", model="claude-sonnet-4-6")
    out = provider.complete("system", "user", max_tokens=100)
    assert out == "claude-says-hi"

    req = route.calls.last.request
    assert req.headers["x-api-key"] == "ak"
    assert req.headers["anthropic-version"] == "2023-06-01"
    body = json.loads(req.content)
    assert body["system"] == "system"
    assert body["messages"][0]["content"] == "user"


@respx.mock
def test_gemini_request_and_parse():
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    route = respx.post(url).mock(
        return_value=httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "gemini-hi"}]}}]}
        )
    )
    provider = GeminiProvider(api_key="gk", model="gemini-2.5-flash")
    out = provider.complete("sys", "usr")
    assert out == "gemini-hi"

    req = route.calls.last.request
    assert req.headers["x-goog-api-key"] == "gk"
    body = json.loads(req.content)
    assert body["system_instruction"]["parts"][0]["text"] == "sys"
    assert body["contents"][0]["parts"][0]["text"] == "usr"


def test_stub_provider_offline():
    out = StubProvider().complete("sys", "Chapter 1 Intro\nbody text")
    assert "Summary" in out
    assert StubProvider(canned="X").complete("a", "b") == "X"


def test_select_provider_precedence(monkeypatch):
    monkeypatch.delenv("BOOK_TO_SKILL_PROVIDER", raising=False)
    assert config.select_provider_name("groq") == "groq"
    monkeypatch.setenv("BOOK_TO_SKILL_PROVIDER", "anthropic")
    assert config.select_provider_name(None) == "anthropic"
    assert config.select_provider_name("gemini") == "gemini"  # flag overrides env
    monkeypatch.delenv("BOOK_TO_SKILL_PROVIDER", raising=False)
    with pytest.raises(config.ConfigError):
        config.select_provider_name(None)
    with pytest.raises(config.ConfigError):
        config.select_provider_name("nope")


def test_build_provider_variants(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    p = config.build_provider("groq")
    assert isinstance(p, OpenAICompatibleProvider)
    assert p.model == "openai/gpt-oss-20b"
    assert p.base_url == "https://api.groq.com/openai/v1"

    monkeypatch.setenv("ANTHROPIC_API_KEY", "ak")
    assert isinstance(config.build_provider("anthropic"), AnthropicProvider)

    monkeypatch.setenv("GEMINI_API_KEY", "gemk")
    assert isinstance(config.build_provider("gemini"), GeminiProvider)

    assert isinstance(config.build_provider("stub"), StubProvider)

    # Ollama needs no key.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert isinstance(config.build_provider("ollama"), OpenAICompatibleProvider)


def test_build_provider_missing_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(config.ConfigError):
        config.build_provider("groq")


def test_estimate_cost():
    assert config.estimate_cost("claude-sonnet-4-6", 1_000_000, 1_000_000) == 18.0
    assert config.estimate_cost("unknown-model", 100, 100) is None
    assert config.estimate_cost(None, 100, 100) is None


def test_build_provider_local_requires_base_url(monkeypatch):
    monkeypatch.delenv("LOCAL_API_KEY", raising=False)
    with pytest.raises(config.ConfigError):
        config.build_provider("local", model="m")  # no base_url
    p = config.build_provider("local", model="m", base_url="http://localhost:9999/v1")
    assert isinstance(p, OpenAICompatibleProvider)


def test_build_provider_missing_keys(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(config.ConfigError):
        config.build_provider("anthropic")
    with pytest.raises(config.ConfigError):
        config.build_provider("gemini")
    with pytest.raises(config.ConfigError):
        config.build_provider("does-not-exist")


def test_load_config_reads_toml(tmp_path, monkeypatch):
    cfg = tmp_path / "bts.toml"
    cfg.write_text('[provider]\nname = "groq"\n', encoding="utf-8")
    monkeypatch.setenv("BOOK_TO_SKILL_CONFIG", str(cfg))
    data = config.load_config()
    assert data["provider"]["name"] == "groq"
    # Missing path -> empty dict.
    monkeypatch.delenv("BOOK_TO_SKILL_CONFIG", raising=False)
    assert config.load_config() == {}
    assert config.load_config(tmp_path / "nope.toml") == {}
