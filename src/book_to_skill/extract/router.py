"""Route a source file to the correct extractor (by suffix, then magic-byte sniff)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ~1.33 tokens per word -> words / 0.75. Named + commented per spec §3.1.
WORDS_PER_TOKEN = 0.75

SUPPORTED_FORMATS = ("pdf", "md", "docx")
_MARKDOWN_SUFFIXES = {".md", ".markdown"}


class UnsupportedFormatError(ValueError):
    """Raised when the input is not one of the supported formats (pdf/md/docx)."""


class MissingDependencyError(RuntimeError):
    """Raised when no extractor backend is available; message lists install commands."""


@dataclass
class ExtractResult:
    """Result of extracting text from a source document."""

    text: str
    format: str
    method: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _sniff_format(path: Path) -> str:
    """Decide format from suffix; fall back to magic bytes when the suffix is unknown."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in _MARKDOWN_SUFFIXES:
        return "md"
    if suffix == ".docx":
        return "docx"

    # Unknown / missing suffix: sniff magic bytes.
    try:
        head = path.read_bytes()[:512]
    except OSError as exc:  # pragma: no cover - filesystem dependent
        raise UnsupportedFormatError(f"Cannot read file: {path}") from exc

    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"PK"):
        # ZIP container. A .docx contains a word/ entry; inspect the archive.
        if _zip_is_docx(path):
            return "docx"
        raise UnsupportedFormatError(
            f"ZIP-based file '{path.name}' is not a .docx "
            f"(supported formats: {', '.join(SUPPORTED_FORMATS)})"
        )
    # Heuristic: decodable-as-UTF-8 text is treated as markdown/plain text.
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UnsupportedFormatError(
            f"Unsupported file '{path.name}'. Supported formats: {', '.join(SUPPORTED_FORMATS)}"
        ) from exc
    return "md"


def _zip_is_docx(path: Path) -> bool:
    """Return True if the ZIP archive looks like an Office Open XML word document."""
    import zipfile

    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
    except (zipfile.BadZipFile, OSError):
        return False
    if "word/document.xml" in names:
        return True
    # Some producers nest content types; require the OOXML marker too.
    return "[Content_Types].xml" in names and any(n.startswith("word/") for n in names)


def _estimate_tokens(words: int) -> int:
    return int(words / WORDS_PER_TOKEN)


def extract(path: str | Path) -> ExtractResult:
    """Extract text + metadata from a pdf/md/docx file.

    Raises:
        FileNotFoundError: the path does not exist.
        UnsupportedFormatError: the file is not pdf/md/docx.
        MissingDependencyError: no backend is installed for the detected format.
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"No such file: {p}")
    if not p.is_file():
        raise UnsupportedFormatError(f"Not a file: {p}")

    fmt = _sniff_format(p)

    # Lazy imports keep module load cheap and avoid circular imports.
    if fmt == "pdf":
        from book_to_skill.extract.pdf import extract_pdf

        text, method, extra = extract_pdf(p)
    elif fmt == "docx":
        from book_to_skill.extract.docx import extract_docx

        text, method, extra = extract_docx(p)
    else:  # md
        from book_to_skill.extract.markdown import extract_markdown

        text, method, extra = extract_markdown(p)

    words = len(text.split())
    chars = len(text)
    size_mb = round(p.stat().st_size / (1024 * 1024), 4)

    metadata: dict[str, Any] = {
        "filename": p.name,
        "source_path": str(p),
        "size_mb": size_mb,
        "format": fmt,
        "method": method,
        "chars": chars,
        "words": words,
        "estimated_tokens": _estimate_tokens(words),
    }
    metadata.update(extra)

    # Merge structure fields (chapters_detected, has_toc, chapter_spans, ...) when available.
    try:
        from book_to_skill.structure import detect_structure

        metadata.update(detect_structure(text, source_format=fmt))
    except Exception:  # pragma: no cover - structure is best-effort metadata
        pass

    return ExtractResult(text=text, format=fmt, method=method, metadata=metadata)
