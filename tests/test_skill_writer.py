"""Skill writer tests: slug, collision, 5 files, valid frontmatter, resolvable links."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from book_to_skill.prompts import choose_style, resolve_style
from book_to_skill.skill_writer import (
    ChapterDoc,
    SkillContent,
    propose_slug,
    resolve_slug,
    slugify,
    write_skill,
)


def _content(slug: str = "widget-handbook") -> SkillContent:
    return SkillContent(
        slug=slug,
        description="Apply widget engineering practices.",
        when_to_use=[f"trigger phrase {i}" for i in range(12)],
        skill_body="# Widget Handbook\n\nCore models.\n\n## Topic Index\n- widgets: ch.1",
        chapters=[
            ChapterDoc(1, "Chapter 1 Introduction", "Intro body about widgets."),
            ChapterDoc(2, "Chapter 2 Patterns", "Factory and observer patterns."),
        ],
        glossary="# Glossary\n\n**Widget** - a composable unit (ch. 1).",
        patterns="# Patterns\n\n- Factory: build widgets.",
        cheatsheet="# Cheatsheet\n\n| When | Do |\n|---|---|\n| many widgets | shard |",
    )


def test_slugify():
    assert slugify("The Pragmatic Programmer!") == "the-pragmatic-programmer"
    assert slugify("  Multiple   spaces  ") == "multiple-spaces"
    assert slugify("") == "untitled"


def test_propose_slug_author_concept():
    assert propose_slug(author_lastname="Martin", core_concept="Clean Code") == "martin-clean-code"
    assert propose_slug(title="Designing Data-Intensive Applications") == (
        "designing-data-intensive-applications"
    )
    assert propose_slug() == "untitled-skill"


def test_collision_appends_suffix(tmp_path: Path):
    (tmp_path / "widget-handbook").mkdir()
    assert resolve_slug("widget-handbook", tmp_path) == "widget-handbook-2"
    (tmp_path / "widget-handbook-2").mkdir()
    assert resolve_slug("widget-handbook", tmp_path) == "widget-handbook-3"
    assert resolve_slug("fresh-slug", tmp_path) == "fresh-slug"


def test_write_skill_creates_all_five_file_types(tmp_path: Path):
    result = write_skill(_content(), skills_root=tmp_path)
    skill_dir = result["skill_dir"]
    assert (skill_dir / "SKILL.md").is_file()
    assert (skill_dir / "glossary.md").is_file()
    assert (skill_dir / "patterns.md").is_file()
    assert (skill_dir / "cheatsheet.md").is_file()
    assert len(result["chapters"]) == 2
    for ch_path in result["chapters"]:
        assert ch_path.is_file()


def test_skill_md_frontmatter_is_valid_yaml(tmp_path: Path):
    result = write_skill(_content(), skills_root=tmp_path)
    raw = result["skill_md"].read_text(encoding="utf-8")
    assert raw.startswith("---\n")
    _, fm, _body = raw.split("---\n", 2)
    meta = yaml.safe_load(fm)
    assert meta["name"] == "widget-handbook"
    assert meta["allowed-tools"] == "Read Grep"
    assert 10 <= len(meta["when_to_use"]) <= 15
    assert "argument-hint" in meta


def test_chapter_links_resolve(tmp_path: Path):
    result = write_skill(_content(), skills_root=tmp_path)
    skill_dir = result["skill_dir"]
    body = result["skill_md"].read_text(encoding="utf-8")
    import re

    links = re.findall(r"\]\((chapters/[^)]+)\)", body)
    assert links, "expected chapter links in SKILL.md"
    for rel in links:
        assert (skill_dir / rel).is_file(), f"broken link: {rel}"


def test_write_skill_refuses_overwrite(tmp_path: Path):
    write_skill(_content(), skills_root=tmp_path)
    with pytest.raises(FileExistsError):
        write_skill(_content(), skills_root=tmp_path)


def test_style_selection():
    code = "```python\ndef f(x):\n    return x->y\n```\nclass A: pass\n" * 3
    prose = "The author argues that teams thrive when they communicate openly. " * 20
    assert choose_style(code) == "technical"
    assert choose_style(prose) == "prose"
    assert resolve_style("auto", code) == "technical"
    assert resolve_style("technical", prose) == "technical"
    with pytest.raises(ValueError):
        resolve_style("bogus", prose)
