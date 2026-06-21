"""Chapter / ToC detection with a 0-chapter window fallback so we always yield sections."""

from __future__ import annotations

import re
from typing import Any

# Tightened heading regex: "Chapter 12", "Part IV", or "3 Something" at line start.
_CHAPTER_RE = re.compile(
    r"^\s*(chapter\s+\d+|part\s+[ivxlcdm]+|\d+\s+[A-Z][a-z])",
    re.IGNORECASE | re.MULTILINE,
)
# Markdown ATX headings, levels 1-2 only (they mark major sections).
_ATX_RE = re.compile(r"^(#{1,2})\s+(.+?)\s*#*$", re.MULTILINE)

_TOC_SCAN_CHARS = 5000
_TOC_KEYWORDS = ("table of contents", "contents")

# Fallback windowing: aim for 6-12 windows, ~3k chars each.
_MIN_WINDOWS = 6
_MAX_WINDOWS = 12
_WINDOW_TARGET_CHARS = 3000

ChapterSpan = tuple[int, int, str]


def _line_title(text: str, start: int) -> str:
    end = text.find("\n", start)
    if end == -1:
        end = len(text)
    return text[start:end].strip()


def _collect_headings(text: str, source_format: str) -> list[tuple[int, str]]:
    positions: dict[int, str] = {}

    if source_format == "md":
        for m in _ATX_RE.finditer(text):
            positions[m.start()] = m.group(2).strip()

    for m in _CHAPTER_RE.finditer(text):
        positions.setdefault(m.start(), _line_title(text, m.start()))

    return sorted(positions.items())


def _spans_from_headings(text: str, headings: list[tuple[int, str]]) -> list[ChapterSpan]:
    spans: list[ChapterSpan] = []
    for i, (start, title) in enumerate(headings):
        end = headings[i + 1][0] if i + 1 < len(headings) else len(text)
        if end > start:
            spans.append((start, end, title or f"Section {i + 1}"))
    return spans


def _window_spans(text: str) -> list[ChapterSpan]:
    n = len(text)
    if n == 0:
        return []
    count = max(_MIN_WINDOWS, min(_MAX_WINDOWS, n // _WINDOW_TARGET_CHARS or _MIN_WINDOWS))
    count = min(count, n)  # never more windows than characters
    size = max(1, n // count)
    spans: list[ChapterSpan] = []
    for i in range(count):
        start = i * size
        end = n if i == count - 1 else min(n, (i + 1) * size)
        if start >= n:
            break
        spans.append((start, end, f"Section {i + 1}"))
    return spans


def _has_toc(text: str) -> bool:
    head = text[:_TOC_SCAN_CHARS].lower()
    return any(kw in head for kw in _TOC_KEYWORDS)


def detect_structure(text: str, source_format: str = "") -> dict[str, Any]:
    """Detect chapters/ToC and return structure fields for metadata.

    Always returns a non-empty ``chapter_spans`` for non-empty input: when no
    chapter headings are found, the text is split into 6-12 equal windows.
    """
    headings = _collect_headings(text, source_format)
    spans = _spans_from_headings(text, headings)

    chapters_detected = len(spans)
    fell_back = False
    if chapters_detected == 0:
        spans = _window_spans(text)
        fell_back = True

    sample = [title for _, _, title in spans][:10]

    return {
        "chapters_detected": chapters_detected,
        "chapter_headings_sample": sample,
        "has_toc": _has_toc(text),
        "chapter_spans": spans,
        "structure_fallback": fell_back,
    }
