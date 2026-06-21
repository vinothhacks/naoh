"""Summarization prompt templates with technical / prose / auto style selection.

The *style* toggle drives summarization only -- it never affects extractor choice
(extractor is picked purely by file format).
"""

from __future__ import annotations

import re

# Token-budget guidance (passed into prompts; not hard string truncation):
CHAPTER_TOKEN_BUDGET = 1200
SKILL_BODY_TOKEN_BUDGET = 4000
GLOSSARY_TOKEN_BUDGET = 1500
PATTERNS_TOKEN_BUDGET = 2000
CHEATSHEET_TOKEN_BUDGET = 1000

_CODE_FENCE_RE = re.compile(r"```|~~~|^\s{4,}\S", re.MULTILINE)
_SYMBOL_RE = re.compile(r"[{}();=<>\[\]]|::|->|=>|\bdef\b|\bclass\b|\bfunction\b")

_STYLE_GUIDANCE = {
    "technical": (
        "Preserve EXACT API names, function/method signatures, parameter names, "
        "code snippets, algorithms, numeric thresholds, and configuration keys. "
        "Prefer fidelity over fluency. Use fenced code blocks for code."
    ),
    "prose": (
        "Preserve the author's arguments, named frameworks/models, concrete examples, "
        "and voice. Keep proper nouns and coined terms exact. Favor crisp explanation "
        "over verbatim quoting."
    ),
}


def choose_style(text: str) -> str:
    """Pick 'technical' or 'prose' from code-block / symbol density."""
    if not text:
        return "prose"
    sample = text[:20000]
    fences = len(_CODE_FENCE_RE.findall(sample))
    symbols = len(_SYMBOL_RE.findall(sample))
    density = (symbols + fences * 50) / max(1, len(sample.split()))
    return "technical" if density > 0.15 or fences >= 2 else "prose"


def resolve_style(style: str, text: str) -> str:
    if style == "auto":
        return choose_style(text)
    if style not in _STYLE_GUIDANCE:
        raise ValueError(f"Unknown style: {style!r} (use technical, prose, or auto)")
    return style


def _guidance(style: str) -> str:
    return _STYLE_GUIDANCE[style]


def chapter_prompt(style: str, title: str, chapter_text: str) -> tuple[str, str]:
    system = (
        "You are a senior technical editor compressing a book chapter into a dense, "
        "reusable reference for an AI coding agent. "
        f"{_guidance(style)} "
        f"Target at most ~{CHAPTER_TOKEN_BUDGET} tokens. Most important content first; "
        "the end may be truncated during compaction."
    )
    user = (
        f"Chapter title: {title}\n\n"
        "Write a dense markdown summary with: key ideas, concrete techniques, any APIs/"
        "code/algorithms, and 'when to apply'. No filler, no preamble.\n\n"
        "----- CHAPTER TEXT -----\n"
        f"{chapter_text}"
    )
    return system, user


def glossary_prompt(style: str, text: str) -> tuple[str, str]:
    system = (
        "Extract a glossary of key terms for an AI coding agent. "
        f"{_guidance(style)} "
        f"Target at most ~{GLOSSARY_TOKEN_BUDGET} tokens."
    )
    user = (
        "Produce an alphabetical markdown glossary. Each entry: **term** - one-line "
        "definition, with a chapter reference like (ch. 3) when inferable.\n\n"
        "----- SOURCE -----\n"
        f"{text}"
    )
    return system, user


def patterns_prompt(style: str, text: str) -> tuple[str, str]:
    system = (
        "Extract reusable techniques, algorithms, and design patterns. "
        f"{_guidance(style)} "
        f"Target at most ~{PATTERNS_TOKEN_BUDGET} tokens."
    )
    user = (
        "Produce a markdown list of patterns/techniques. For each: name, problem it "
        "solves, how to apply, and trade-offs.\n\n"
        "----- SOURCE -----\n"
        f"{text}"
    )
    return system, user


def cheatsheet_prompt(style: str, text: str) -> tuple[str, str]:
    system = (
        "Build a quick-reference cheatsheet for an AI coding agent. "
        f"{_guidance(style)} "
        f"Target at most ~{CHEATSHEET_TOKEN_BUDGET} tokens."
    )
    user = (
        "Produce decision tables and quick rules in markdown. Prefer tables. "
        "No long prose.\n\n"
        "----- SOURCE -----\n"
        f"{text}"
    )
    return system, user


def skill_body_prompt(
    style: str, title: str, chapter_titles: list[str], overview_text: str
) -> tuple[str, str]:
    system = (
        "You are writing the body of a Claude Code SKILL.md: the front-loaded core "
        "mental models plus a topic index for a book-derived skill. "
        f"{_guidance(style)} "
        f"Target at most ~{SKILL_BODY_TOKEN_BUDGET} tokens, most important content first "
        "(compaction truncates the end). Do NOT include YAML frontmatter; that is added "
        "separately. Do NOT include a chapter index; that is appended separately."
    )
    chapters_list = "\n".join(f"- {t}" for t in chapter_titles)
    user = (
        f"Book/skill title: {title}\n\n"
        f"Chapters:\n{chapters_list}\n\n"
        "Write markdown with: a 2-3 sentence purpose, the core mental models a "
        "practitioner must hold, and a '## Topic Index' mapping topics to the chapters "
        "that cover them.\n\n"
        "----- OVERVIEW / FRONT MATTER -----\n"
        f"{overview_text}"
    )
    return system, user
