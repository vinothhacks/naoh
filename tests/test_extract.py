"""Extraction routing + backend tests (offline, no network)."""

from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from book_to_skill.extract import (
    MissingDependencyError,
    UnsupportedFormatError,
    extract,
)
from book_to_skill.extract import pdf as pdf_mod
from book_to_skill.extract.docx import _stdlib_docx, extract_docx
from book_to_skill.extract.router import _sniff_format


def test_markdown_passthrough(sample_md: Path):
    result = extract(sample_md)
    assert result.format == "md"
    assert result.method == "read"
    assert "Widget" in result.text
    assert result.metadata["words"] > 0
    assert result.metadata["estimated_tokens"] == int(result.metadata["words"] / 0.75)
    assert result.metadata["filename"] == "sample.md"


def test_docx_extraction(sample_docx: Path):
    result = extract(sample_docx)
    assert result.format == "docx"
    assert "Chapter 1 Introduction" in result.text
    assert result.metadata["paragraph_count"] >= 6


def test_docx_stdlib_fallback_only(sample_docx: Path):
    text, method, extra = _stdlib_docx(sample_docx)
    assert method == "stdlib-zipfile"
    assert "Anti-patterns" in text
    assert extra["paragraph_count"] >= 6


def test_docx_router_falls_back_when_python_docx_missing(sample_docx: Path, monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "docx":
            raise ImportError("simulated missing python-docx")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    text, method, _ = extract_docx(sample_docx)
    assert method == "stdlib-zipfile"
    assert "Chapter 2 Patterns" in text


def test_suffix_routing(tmp_path: Path):
    pdfp = tmp_path / "a.pdf"
    pdfp.write_bytes(b"%PDF-1.4 fake")
    assert _sniff_format(pdfp) == "pdf"
    mdp = tmp_path / "a.markdown"
    mdp.write_text("# hi", encoding="utf-8")
    assert _sniff_format(mdp) == "md"


def test_magic_byte_routing_for_unknown_suffix(tmp_path: Path):
    # PDF magic bytes with a non-pdf suffix.
    weird = tmp_path / "book.bin"
    weird.write_bytes(b"%PDF-1.7\n...")
    assert _sniff_format(weird) == "pdf"

    # UTF-8 text with unknown suffix -> markdown.
    txt = tmp_path / "notes.bin"
    txt.write_text("# Title\nbody", encoding="utf-8")
    assert _sniff_format(txt) == "md"


def test_unsupported_binary_rejected(tmp_path: Path):
    blob = tmp_path / "img.bin"
    blob.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x01\x02\x03\xff\xfe")
    with pytest.raises(UnsupportedFormatError):
        extract(blob)


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        extract("does-not-exist-xyz.md")


def test_markdown_bom_is_stripped(tmp_path: Path):
    # A UTF-8 BOM must not break heading detection.
    p = tmp_path / "bom.md"
    p.write_bytes("\ufeff# Title\n\nbody\n".encode())
    result = extract(p)
    assert result.text.startswith("# Title")
    assert "\ufeff" not in result.text


def test_pdf_missing_all_backends_raises(tmp_path: Path, monkeypatch):
    pdfp = tmp_path / "scanned.pdf"
    pdfp.write_bytes(b"%PDF-1.4 minimal")

    # No backend yields text, and none are installed.
    monkeypatch.setattr(pdf_mod, "_try_pdftotext", lambda p: None)
    monkeypatch.setattr(pdf_mod, "_try_pypdf", lambda p: None)
    monkeypatch.setattr(pdf_mod, "_try_pdfminer", lambda p: None)
    monkeypatch.setattr(pdf_mod, "_any_backend_installed", lambda: False)

    with pytest.raises(MissingDependencyError) as exc:
        pdf_mod.extract_pdf(pdfp)
    assert "pip install pypdf" in str(exc.value)


def test_pdf_real_blank_backends(blank_pdf: Path):
    # Exercises the real pypdf/pdfminer code paths deterministically.
    assert pdf_mod._any_backend_installed() is True
    assert pdf_mod._page_count(blank_pdf) == 1
    assert pdf_mod._try_pypdf(blank_pdf) is None  # blank page -> no text
    text, method, extra = pdf_mod.extract_pdf(blank_pdf)
    assert method == "none"
    assert text == ""
    assert extra["page_count"] == 1
    assert "warning" in extra


def test_extract_blank_pdf_via_router(blank_pdf: Path):
    result = extract(blank_pdf)
    assert result.format == "pdf"
    assert result.metadata["page_count"] == 1
    # Structure detection still runs on empty text (yields no chapters).
    assert result.metadata["chapters_detected"] == 0


def test_pdf_uses_first_nonempty_backend(tmp_path: Path, monkeypatch):
    pdfp = tmp_path / "book.pdf"
    pdfp.write_bytes(b"%PDF-1.4 minimal")

    monkeypatch.setattr(pdf_mod, "_try_pdftotext", lambda p: None)
    monkeypatch.setattr(pdf_mod, "_try_pypdf", lambda p: "Chapter 1\nHello from pypdf")
    monkeypatch.setattr(pdf_mod, "_try_pdfminer", lambda p: "should not be used")
    monkeypatch.setattr(pdf_mod, "_page_count", lambda p: 3)

    text, method, extra = pdf_mod.extract_pdf(pdfp)
    assert method == "pypdf"
    assert "Hello from pypdf" in text
    assert extra["page_count"] == 3
