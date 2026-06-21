"""End-to-end pipeline tests using the offline StubProvider (no network)."""

from __future__ import annotations

from pathlib import Path

import yaml

from book_to_skill.extract import extract
from book_to_skill.generate import generate_skill
from book_to_skill.providers.stub import StubProvider


def test_e2e_build_markdown_into_temp_root(sample_md: Path, tmp_path: Path):
    skills_root = tmp_path / "skills"
    res = extract(sample_md)
    expected_chapters = len(res.metadata["chapter_spans"])

    result = generate_skill(
        extract_result=res,
        provider=StubProvider(),
        style="auto",
        slug="widget-handbook",
        skills_root=skills_root,
    )

    skill_dir = result["skill_dir"]
    assert skill_dir == skills_root / "widget-handbook"
    assert (skill_dir / "SKILL.md").is_file()
    assert (skill_dir / "glossary.md").is_file()
    assert (skill_dir / "patterns.md").is_file()
    assert (skill_dir / "cheatsheet.md").is_file()

    chapter_files = sorted((skill_dir / "chapters").glob("*.md"))
    assert len(chapter_files) == expected_chapters

    for cf in chapter_files:
        size = cf.stat().st_size
        assert 30 < size < 50_000, f"{cf.name} size {size} out of range"

    raw = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    _, fm, body = raw.split("---\n", 2)
    meta = yaml.safe_load(fm)
    assert meta["name"] == "widget-handbook"
    assert 10 <= len(meta["when_to_use"]) <= 15
    assert "## Chapter Index" in body
    # Every chapter link resolves.
    import re

    for rel in re.findall(r"\]\((chapters/[^)]+)\)", body):
        assert (skill_dir / rel).is_file()


def test_e2e_zero_chapter_source_yields_windows(tmp_path: Path):
    src = tmp_path / "flat.md"
    src.write_text("plain text with no headings at all. " * 400, encoding="utf-8")
    skills_root = tmp_path / "skills"

    result = generate_skill(
        source_path=src,
        provider=StubProvider(),
        slug="flat-doc",
        skills_root=skills_root,
    )
    chapter_files = list((result["skill_dir"] / "chapters").glob("*.md"))
    assert 6 <= len(chapter_files) <= 12


def test_e2e_collision_creates_suffixed_skill(sample_md: Path, tmp_path: Path):
    skills_root = tmp_path / "skills"
    res = extract(sample_md)
    first = generate_skill(
        extract_result=res, provider=StubProvider(), slug="dup", skills_root=skills_root
    )
    second = generate_skill(
        extract_result=res, provider=StubProvider(), slug="dup", skills_root=skills_root
    )
    assert first["slug"] == "dup"
    assert second["slug"] == "dup-2"
    assert (skills_root / "dup").is_dir()
    assert (skills_root / "dup-2").is_dir()
