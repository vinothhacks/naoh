"""DOCX extraction: python-docx -> stdlib zipfile XML fallback (zero third-party deps)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# WordprocessingML namespace.
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _try_python_docx(path: Path) -> tuple[str, str, dict] | None:
    try:
        import docx  # python-docx
    except ImportError:
        return None
    try:
        document = docx.Document(str(path))
    except Exception:
        return None
    paragraphs = [p.text for p in document.paragraphs]
    text = "\n".join(paragraphs).strip()
    return text, "python-docx", {"paragraph_count": len(paragraphs)}


def _stdlib_docx(path: Path) -> tuple[str, str, dict]:
    """Parse word/document.xml with the stdlib only.

    Concatenates <w:t> runs, inserting a newline at each <w:p> paragraph boundary.
    """
    with zipfile.ZipFile(path) as zf:
        xml_bytes = zf.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    paragraphs: list[str] = []
    for para in root.iter(f"{_W_NS}p"):
        runs = [node.text or "" for node in para.iter(f"{_W_NS}t")]
        paragraphs.append("".join(runs))
    text = "\n".join(paragraphs).strip()
    # Collapse runs of 3+ blank lines that some producers emit.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, "stdlib-zipfile", {"paragraph_count": len(paragraphs)}


def extract_docx(path: Path) -> tuple[str, str, dict]:
    """Return (text, method, extra_metadata) for a .docx file.

    Prefers python-docx; falls back to a stdlib-only parser so extraction works
    with zero third-party dependencies installed.
    """
    via_lib = _try_python_docx(path)
    if via_lib is not None and via_lib[0].strip():
        return via_lib
    return _stdlib_docx(path)
