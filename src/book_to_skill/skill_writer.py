"""Write the 5 Claude Code skill files: slugging, collision handling, valid frontmatter."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def default_skills_root() -> Path:
    """The Claude Code skills directory: ~/.claude/skills."""
    return Path.home() / ".claude" / "skills"


def slugify(value: str, max_len: int = 60) -> str:
    value = (value or "").lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    value = value[:max_len].strip("-")
    return value or "untitled"


def propose_slug(
    *,
    author_lastname: str | None = None,
    core_concept: str | None = None,
    title: str | None = None,
) -> str:
    """Propose author-concept when there's a strong methodological identity, else title-based."""
    if author_lastname and core_concept:
        return f"{slugify(author_lastname)}-{slugify(core_concept)}"
    if title:
        return slugify(title)
    if core_concept:
        return slugify(core_concept)
    return "untitled-skill"


def resolve_slug(slug: str, skills_root: Path, *, interactive: bool = False) -> str:
    """Return a non-colliding slug. Never overwrites; appends -2, -3, ... on collision."""
    slug = slugify(slug)
    target = skills_root / slug
    if not target.exists():
        return slug
    if interactive:  # pragma: no cover - CLI handles the prompt path
        raise FileExistsError(f"Skill already exists: {target}")
    n = 2
    while (skills_root / f"{slug}-{n}").exists():
        n += 1
    return f"{slug}-{n}"


@dataclass
class ChapterDoc:
    index: int
    title: str
    body: str


@dataclass
class SkillContent:
    """Fully-synthesized skill content, ready to be written to disk."""

    slug: str
    description: str
    when_to_use: list[str]
    skill_body: str  # mental models + topic index (chapter index is appended automatically)
    chapters: list[ChapterDoc] = field(default_factory=list)
    glossary: str = ""
    patterns: str = ""
    cheatsheet: str = ""
    argument_hint: str = "[topic or question]"
    name: str | None = None  # display name; defaults to slug


def _frontmatter(content: SkillContent) -> str:
    data: dict[str, Any] = {
        "name": content.name or content.slug,
        "description": content.description,
        "when_to_use": list(content.when_to_use),
        "allowed-tools": "Read Grep",
        "argument-hint": content.argument_hint,
    }
    dumped = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000)
    return f"---\n{dumped}---\n"


def _chapter_filename(ch: ChapterDoc) -> str:
    return f"ch{ch.index:02d}-{slugify(ch.title, max_len=40)}.md"


def _chapter_index_md(chapters: list[ChapterDoc]) -> str:
    if not chapters:
        return ""
    lines = ["", "## Chapter Index", ""]
    for ch in chapters:
        rel = f"chapters/{_chapter_filename(ch)}"
        lines.append(f"- [{ch.title}]({rel})")
    lines.append("")
    return "\n".join(lines)


def write_skill(content: SkillContent, skills_root: Path | None = None) -> dict[str, Any]:
    """Write SKILL.md + chapters/ + glossary/patterns/cheatsheet. Returns written paths.

    The caller is responsible for collision-resolving ``content.slug`` first
    (via ``resolve_slug``); this function will not overwrite an existing skill.
    """
    root = skills_root or default_skills_root()
    skill_dir = root / content.slug
    if skill_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing skill: {skill_dir}")

    chapters_dir = skill_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    chapter_paths: list[Path] = []
    for ch in content.chapters:
        path = chapters_dir / _chapter_filename(ch)
        body = ch.body if ch.body.lstrip().startswith("#") else f"# {ch.title}\n\n{ch.body}"
        path.write_text(body.rstrip() + "\n", encoding="utf-8")
        chapter_paths.append(path)

    skill_md = skill_dir / "SKILL.md"
    body = content.skill_body.rstrip() + "\n" + _chapter_index_md(content.chapters)
    skill_md.write_text(_frontmatter(content) + "\n" + body.lstrip("\n"), encoding="utf-8")

    glossary = skill_dir / "glossary.md"
    glossary.write_text((content.glossary or "# Glossary\n").rstrip() + "\n", encoding="utf-8")

    patterns = skill_dir / "patterns.md"
    patterns.write_text((content.patterns or "# Patterns\n").rstrip() + "\n", encoding="utf-8")

    cheatsheet = skill_dir / "cheatsheet.md"
    cheatsheet.write_text(
        (content.cheatsheet or "# Cheatsheet\n").rstrip() + "\n", encoding="utf-8"
    )

    return {
        "skill_dir": skill_dir,
        "skill_md": skill_md,
        "chapters": chapter_paths,
        "glossary": glossary,
        "patterns": patterns,
        "cheatsheet": cheatsheet,
        "slug": content.slug,
    }
