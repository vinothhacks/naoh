"""PDF extraction: pdftotext (poppler) -> pypdf -> pdfminer.six (first non-empty wins)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from book_to_skill.extract.router import MissingDependencyError

_PDFTOTEXT_TIMEOUT_S = 120

_INSTALL_HINT = (
    "No PDF extractor is available. Install at least one backend:\n"
    "  - poppler (best layout):  sudo apt install poppler-utils   "
    "(macOS: brew install poppler; Windows: choco install poppler)\n"
    "  - pypdf:                  pip install pypdf\n"
    "  - pdfminer.six:           pip install pdfminer.six"
)


def _try_pdftotext(path: Path) -> str | None:
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    try:
        proc = subprocess.run(  # noqa: S603 - fixed exe resolved via PATH
            [exe, "-layout", str(path), "-"],
            capture_output=True,
            timeout=_PDFTOTEXT_TIMEOUT_S,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    text = proc.stdout.decode("utf-8", errors="replace")
    return text if text.strip() else None


def _try_pypdf(path: Path) -> str | None:
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        reader = PdfReader(str(path))
        parts = [(page.extract_text() or "") for page in reader.pages]
    except Exception:
        return None
    text = "\n".join(parts)
    return text if text.strip() else None


def _try_pdfminer(path: Path) -> str | None:
    try:
        from pdfminer.high_level import extract_text as _miner_extract
    except ImportError:
        return None
    try:
        text = _miner_extract(str(path))
    except Exception:
        return None
    return text if text and text.strip() else None


def _page_count(path: Path) -> int | None:
    exe = shutil.which("pdfinfo")
    if exe:
        try:
            proc = subprocess.run(  # noqa: S603 - fixed exe resolved via PATH
                [exe, str(path)],
                capture_output=True,
                timeout=30,
                check=False,
            )
            if proc.returncode == 0:
                for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
                    if line.lower().startswith("pages:"):
                        return int(line.split(":", 1)[1].strip())
        except (subprocess.TimeoutExpired, OSError, ValueError):
            pass
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception:
        return None


def extract_pdf(path: Path) -> tuple[str, str, dict]:
    """Return (text, method, extra_metadata) for a PDF.

    Tries backends in order and uses the first that yields non-empty text.
    """
    backends = (
        ("pdftotext", _try_pdftotext),
        ("pypdf", _try_pypdf),
        ("pdfminer", _try_pdfminer),
    )

    for method, fn in backends:
        # Probe availability lazily inside each backend; treat None as "no text / unavailable".
        text = fn(path)
        if text is None:
            continue
        return text, method, {"page_count": _page_count(path)}

    # Distinguish "no backend installed" from "backends installed but no text".
    if not _any_backend_installed():
        raise MissingDependencyError(_INSTALL_HINT)
    # A backend ran but produced nothing (e.g. scanned/image-only PDF).
    return (
        "",
        "none",
        {"page_count": _page_count(path), "warning": "no extractable text (image-only PDF?)"},
    )


def _any_backend_installed() -> bool:
    if shutil.which("pdftotext"):
        return True
    try:
        import pypdf  # noqa: F401

        return True
    except ImportError:
        pass
    try:
        import pdfminer  # noqa: F401

        return True
    except ImportError:
        return False
