"""Structure detection tests: chapter/ToC detection + 0-chapter window fallback."""

from __future__ import annotations

from pathlib import Path

from book_to_skill.extract import extract
from book_to_skill.structure import detect_structure


def test_detects_markdown_chapters(sample_md: Path):
    text = sample_md.read_text(encoding="utf-8")
    result = detect_structure(text, source_format="md")
    assert result["chapters_detected"] >= 3
    assert result["structure_fallback"] is False
    titles = " ".join(result["chapter_headings_sample"])
    assert "Chapter 1 Introduction" in titles
    # Spans must be ordered and non-overlapping.
    spans = result["chapter_spans"]
    for (s1, e1, _), (s2, _, _) in zip(spans, spans[1:], strict=False):
        assert s1 < e1 <= s2


def test_detects_chapter_headings_in_plain_text():
    text = "Chapter 1 Alpha\nbody one\nChapter 2 Beta\nbody two\nChapter 3 Gamma\nbody three\n"
    result = detect_structure(text, source_format="pdf")
    assert result["chapters_detected"] == 3
    assert result["chapter_headings_sample"][0] == "Chapter 1 Alpha"


def test_toc_detection():
    text = "Preface\n\nTable of Contents\n1. Intro .... 1\n2. Body .... 9\n\nChapter 1 Intro\nx"
    result = detect_structure(text, source_format="pdf")
    assert result["has_toc"] is True


def test_zero_chapter_fallback_yields_windows():
    # No chapter headings anywhere -> must still produce 6-12 sections.
    text = ("lorem ipsum dolor sit amet " * 2000).strip()
    result = detect_structure(text, source_format="pdf")
    assert result["chapters_detected"] == 0
    assert result["structure_fallback"] is True
    n = len(result["chapter_spans"])
    assert 6 <= n <= 12
    # Windows cover the whole text contiguously.
    spans = result["chapter_spans"]
    assert spans[0][0] == 0
    assert spans[-1][1] == len(text)
    for (_, e1, _), (s2, _, _) in zip(spans, spans[1:], strict=False):
        assert e1 == s2


def test_short_zero_chapter_input_still_yields_sections():
    result = detect_structure("a short note with no headings at all", source_format="pdf")
    assert result["structure_fallback"] is True
    assert len(result["chapter_spans"]) >= 1


def test_router_merges_structure_into_metadata(sample_md: Path):
    result = extract(sample_md)
    assert "chapters_detected" in result.metadata
    assert "chapter_spans" in result.metadata
    assert result.metadata["chapters_detected"] >= 3
