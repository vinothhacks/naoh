"""Markdown / plain-text extraction: read UTF-8, keep headings (they drive structure)."""

from __future__ import annotations

from pathlib import Path


def extract_markdown(path: Path) -> tuple[str, str, dict]:
    """Return (text, method, extra_metadata) for a markdown/plain-text file.

    Headings are preserved verbatim because structure detection relies on them.
    """
    # utf-8-sig transparently strips a leading BOM if present (common on Windows).
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    # Normalize Windows newlines so downstream regex/offsets are consistent.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Defensively drop any stray BOM characters that survived (e.g. mid-stream).
    text = text.replace("\ufeff", "")
    heading_count = sum(1 for line in text.splitlines() if line.lstrip().startswith("#"))
    return text, "read", {"heading_count": heading_count}
