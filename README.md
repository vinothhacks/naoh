# naoh — book-to-skill

[![CI](https://github.com/vinothhacks/naoh/actions/workflows/ci.yml/badge.svg)](https://github.com/vinothhacks/naoh/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

Turn a technical **book or document** (`.pdf`, `.md`/`.markdown`, `.docx`) into a
[Claude Code skill](https://code.claude.com/docs/en/skills): a front-loaded `SKILL.md`
plus on-demand chapter summaries, a glossary, a patterns file, and a cheatsheet.

`naoh` is an enhanced reimplementation of the public reference
[`virgiliojr94/book-to-skill`](https://github.com/virgiliojr94/book-to-skill). The package
and CLI keep the name `book-to-skill`; the project/brand is **naoh**.

## Two modes, one core

Extraction + structure detection are shared. What differs is who writes the summaries:

| Mode | API key? | Who synthesizes | How to trigger |
| --- | --- | --- | --- |
| **Skill mode** (default) | No | The Claude Code agent, by following `SKILL.md` | install the skill, then `/book-to-skill <file> [slug]` |
| **API mode** | Yes | A configurable LLM provider, in our Python code | `book-to-skill build <file> [slug] --provider <name>` |

### Output (same in both modes)

```
~/.claude/skills/<slug>/
├── SKILL.md            # core mental models + chapter index + topic index (front-loaded)
├── chapters/chNN-*.md  # one dense summary per chapter (loaded on demand)
├── glossary.md         # key terms, alphabetical, with chapter refs
├── patterns.md         # techniques / algorithms / design patterns
└── cheatsheet.md       # decision tables + quick rules
```

## Supported input formats

Only three, by design — anything else is rejected with a clear message:

- **PDF** (`.pdf`) — `pdftotext -layout` (poppler) → `pypdf` → `pdfminer.six` (first non-empty wins).
- **Markdown** (`.md`, `.markdown`) — read as UTF-8 (BOM-safe); headings drive structure detection.
- **DOCX** (`.docx`) — `python-docx`, with a zero-dependency stdlib `zipfile` XML fallback.

Routing is by file suffix, with a magic-byte sniff fallback (`%PDF`, ZIP→docx) when the suffix is
missing or wrong. If a backend is missing, the tool prints the exact install commands and exits
non-zero (it never fails silently).

## Install

```bash
pip install naoh            # from PyPI
```

The PyPI distribution is **`naoh`**; it installs the `book_to_skill` import package and the
`book-to-skill` CLI command.

From a clone (for development):

```bash
pip install -e ".[dev]"     # with dev/test extras
# or, for runtime only:
pip install -e .
```

Python 3.11+ required. PDF live extraction works best with poppler (`pdftotext`); without it the
tool falls back to `pypdf` / `pdfminer.six`.

## Usage

```bash
# 1) Extract only — writes full_text.txt + metadata.json, prints their paths (used by skill mode)
book-to-skill extract path/to/book.pdf

# 2) Analyze — extraction + structure report, no files written
book-to-skill analyze path/to/book.pdf

# 3) Build (API mode) — generate the whole skill with a provider
book-to-skill build path/to/book.pdf my-slug --provider groq --model openai/gpt-oss-20b
```

Useful flags for `build`: `--style {technical,prose,auto}`, `--base-url` (for `local`/custom),
`--analyze-only`, `--skills-root <dir>`, `--yes` (skip the confirmation prompt).

### Skill mode (no API key)

Install the skill, then invoke it from Claude Code:

```
/book-to-skill ~/Documents/some-book.pdf clean-architecture
```

The agent runs `scripts/extract.py`, reads the extracted text, and writes the five files itself.

## Providers (API mode)

One OpenAI-compatible adapter (switched by `base_url`) plus dedicated Anthropic and Gemini adapters.
Selection precedence: `--provider` flag → `BOOK_TO_SKILL_PROVIDER` env → error.

| Provider | `--provider` | Base URL | Env var | Default model |
| --- | --- | --- | --- | --- |
| OpenAI | `openai` | `https://api.openai.com/v1` | `OPENAI_API_KEY` | `gpt-4o-mini` |
| OpenRouter | `openrouter` | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | `openai/gpt-4o-mini` |
| Groq | `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` | `openai/gpt-oss-20b` |
| xAI Grok | `grok` | `https://api.x.ai/v1` | `XAI_API_KEY` | `grok-2-latest` |
| DeepSeek | `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` | `deepseek-chat` |
| Qwen / DashScope | `qwen` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | `DASHSCOPE_API_KEY` | `qwen-plus` |
| Ollama (local) | `ollama` | `http://localhost:11434/v1` | _(none)_ | `llama3.2` |
| Local / custom | `local` | `--base-url` | `LOCAL_API_KEY` _(optional)_ | `--model` |
| Anthropic (Claude) | `anthropic` | `https://api.anthropic.com/v1/messages` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| Google Gemini | `gemini` | `https://generativelanguage.googleapis.com/v1beta` | `GEMINI_API_KEY` | `gemini-2.5-flash` |

Gemini also exposes an OpenAI-compatible endpoint
(`https://generativelanguage.googleapis.com/v1beta/openai/`); this project ships a dedicated native
adapter but you can also drive Gemini through `local` with that base URL.

> **Pricing/model IDs drift.** Cost estimates use a config-driven table in
> `src/book_to_skill/config.py` (`MODEL_PRICES`). Verify current pricing at
> <https://docs.claude.com/en/docs/about-claude/pricing> and each provider's pricing page.

Keys are read from environment variables only and are **never** logged or committed. Copy
`.env.example` to `.env` and fill in what you use.

## Development

```bash
ruff check .            # lint
ruff format --check .   # format check
pytest -q --cov=book_to_skill --cov-report=term-missing
```

All tests are offline: synthetic fixtures are built at runtime (including a stdlib-only DOCX and a
`pypdf`-built PDF), provider HTTP is mocked, and the end-to-end test uses a hidden `stub` provider.
CI runs ruff + pytest on Python 3.11 and 3.12.

## License

MIT — see [LICENSE](LICENSE).
