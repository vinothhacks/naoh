"""API-mode orchestration: extract -> per-chapter summaries -> skill files."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from book_to_skill.extract import ExtractResult, extract
from book_to_skill.prompts import (
    chapter_prompt,
    cheatsheet_prompt,
    glossary_prompt,
    patterns_prompt,
    resolve_style,
    skill_body_prompt,
)
from book_to_skill.providers.base import LLMProvider
from book_to_skill.skill_writer import (
    ChapterDoc,
    SkillContent,
    propose_slug,
    resolve_slug,
    slugify,
    write_skill,
)

# Per-chapter input cap so a single huge chapter cannot blow up the request size.
MAX_CHAPTER_CHARS = 16000
OVERVIEW_CHARS = 6000

_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _derive_title(text: str, meta: dict[str, Any]) -> str:
    m = _H1_RE.search(text[:2000])
    if m:
        return m.group(1).strip()
    stem = Path(meta.get("filename", "skill")).stem
    return stem.replace("-", " ").replace("_", " ").strip().title() or "Untitled"


def _default_triggers(title: str, chapters: list[ChapterDoc]) -> list[str]:
    """Build 10-15 trigger phrases for the skill's when_to_use."""
    short = title.lower()
    triggers = [
        f"questions about {short}",
        f"applying ideas from {short}",
        f"how does {short} recommend doing this",
        f"best practices from {short}",
        f"summarize a concept from {short}",
        f"what does {short} say about a topic",
    ]
    for ch in chapters[:8]:
        topic = re.sub(r"^(chapter|part|section)\s+[\divxlcdm]+\s*", "", ch.title, flags=re.I)
        topic = topic.strip() or ch.title
        triggers.append(f"about {topic.lower()}")
    # De-dupe while preserving order, then clamp to 10-15.
    seen: set[str] = set()
    unique = [t for t in triggers if not (t in seen or seen.add(t))]
    if len(unique) < 10:
        unique += [f"reference material on {short}"] * (10 - len(unique))
    return unique[:15]


def generate_skill(
    source_path: str | Path | None = None,
    *,
    provider: LLMProvider,
    extract_result: ExtractResult | None = None,
    style: str = "auto",
    slug: str | None = None,
    skills_root: Path | None = None,
    on_log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run the full API-mode pipeline and write the skill. Returns written paths."""
    log = on_log or (lambda _msg: None)

    res = extract_result or extract(source_path)  # type: ignore[arg-type]
    text = res.text
    meta = res.metadata
    if not text.strip():
        raise ValueError("Extracted text is empty; cannot generate a skill.")

    eff_style = resolve_style(style, text)
    title = _derive_title(text, meta)
    spans = list(meta.get("chapter_spans") or [])
    log(f"Style: {eff_style}; chapters/sections: {len(spans)}")

    chapters: list[ChapterDoc] = []
    for i, (start, end, ch_title) in enumerate(spans, start=1):
        chunk = text[start:end][:MAX_CHAPTER_CHARS]
        sys_p, usr_p = chapter_prompt(eff_style, ch_title, chunk)
        body = provider.complete(sys_p, usr_p, max_tokens=1600, temperature=0.2)
        chapters.append(ChapterDoc(index=i, title=ch_title, body=body))
        log(f"  chapter {i}/{len(spans)}: {ch_title}")

    overview = text[:OVERVIEW_CHARS]
    glossary = provider.complete(*glossary_prompt(eff_style, overview), max_tokens=2000)
    patterns = provider.complete(*patterns_prompt(eff_style, overview), max_tokens=2600)
    cheatsheet = provider.complete(*cheatsheet_prompt(eff_style, overview), max_tokens=1500)
    skill_body = provider.complete(
        *skill_body_prompt(eff_style, title, [c.title for c in chapters], overview),
        max_tokens=4500,
    )

    root = skills_root
    proposed = slug or propose_slug(title=title)
    from book_to_skill.skill_writer import default_skills_root

    resolved = resolve_slug(proposed, root or default_skills_root())

    content = SkillContent(
        slug=resolved,
        description=(
            f"Distilled from '{title}': apply its concepts, terms, and patterns while coding."
        ),
        when_to_use=_default_triggers(title, chapters),
        skill_body=skill_body,
        chapters=chapters,
        glossary=glossary,
        patterns=patterns,
        cheatsheet=cheatsheet,
        argument_hint="[topic or question]",
        name=resolved,
    )
    result = write_skill(content, root)
    log(f"Wrote skill '{resolved}' ({len(chapters)} chapters) to {result['skill_dir']}")
    return result


def analyze_only(source_path: str | Path) -> dict[str, Any]:
    """Offline extraction + structure report (no LLM calls, no files written)."""
    res = extract(source_path)
    text = res.text
    meta = res.metadata
    lower = text.lower()
    report = {
        "title": _derive_title(text, meta),
        "format": meta.get("format"),
        "method": meta.get("method"),
        "words": meta.get("words"),
        "estimated_tokens": meta.get("estimated_tokens"),
        "pages_or_sections": meta.get("page_count") or meta.get("paragraph_count"),
        "has_toc": meta.get("has_toc"),
        "chapters_detected": meta.get("chapters_detected"),
        "structure_fallback": meta.get("structure_fallback"),
        "chapter_headings_sample": meta.get("chapter_headings_sample", []),
        "signal_counts": {
            "patterns": lower.count("pattern"),
            "principles": lower.count("principle"),
            "frameworks": lower.count("framework"),
            "anti_patterns": lower.count("anti-pattern") + lower.count("antipattern"),
        },
        "slug_suggestion": slugify(_derive_title(text, meta)),
    }
    return report
