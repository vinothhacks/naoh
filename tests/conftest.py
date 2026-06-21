"""Shared fixtures, built at runtime so the repo needs no committed binaries / no network."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

SAMPLE_MD = """# The Widget Handbook

A practical guide to widgets.

## Chapter 1 Introduction

Widgets are small composable units. This chapter explains why widgets matter
and introduces the `Widget` class and its `assemble()` method.

## Chapter 2 Patterns

The factory pattern builds widgets. The observer pattern notifies on change.
Use a threshold of 100 widgets before sharding.

## Chapter 3 Anti-patterns

Avoid the god-widget. Avoid blocking the assemble() call on network IO.
"""

# Minimal-but-valid Office Open XML parts so BOTH python-docx and the stdlib
# fallback can read the document.
_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.'
    'wordprocessingml.document.main+xml"/>'
    "</Types>"
)

_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/>'
    "</Relationships>"
)

_DOCX_PARAGRAPHS = [
    "Chapter 1 Introduction",
    "Widgets are small composable units and this is the intro.",
    "Chapter 2 Patterns",
    "The factory pattern builds widgets; the observer pattern notifies.",
    "Chapter 3 Anti-patterns",
    "Avoid the god-widget and avoid blocking on network IO.",
]


def _docx_document_xml(paragraphs: list[str]) -> str:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        "<w:document "
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )


def build_sample_md(target: Path) -> Path:
    target.write_text(SAMPLE_MD, encoding="utf-8")
    return target


def build_sample_docx(target: Path, paragraphs: list[str] | None = None) -> Path:
    paragraphs = paragraphs or _DOCX_PARAGRAPHS
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS)
        zf.writestr("word/document.xml", _docx_document_xml(paragraphs))
    return target


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    return build_sample_md(tmp_path / "sample.md")


@pytest.fixture
def sample_docx(tmp_path: Path) -> Path:
    return build_sample_docx(tmp_path / "sample.docx")


@pytest.fixture
def docx_paragraphs() -> list[str]:
    return list(_DOCX_PARAGRAPHS)


@pytest.fixture
def blank_pdf(tmp_path: Path) -> Path:
    """A real, valid single-page PDF with no extractable text (pypdf-built)."""
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    target = tmp_path / "blank.pdf"
    with target.open("wb") as fh:
        writer.write(fh)
    return target
