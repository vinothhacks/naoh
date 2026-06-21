#!/usr/bin/env python3
"""Thin shim used by SKILL.md (skill mode).

Extracts text + metadata from a pdf/md/docx and writes ``full_text.txt`` and
``metadata.json`` into a temp dir (or ``--out``), then prints both paths.

Works whether or not the package is pip-installed: it adds the repo's ``src/``
to ``sys.path`` as a fallback.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path


def _ensure_importable() -> None:
    try:
        import book_to_skill  # noqa: F401

        return
    except ImportError:
        src = Path(__file__).resolve().parent.parent / "src"
        if src.is_dir():
            sys.path.insert(0, str(src))


def main(argv: list[str] | None = None) -> int:
    _ensure_importable()
    from book_to_skill.extract import (
        MissingDependencyError,
        UnsupportedFormatError,
        extract,
    )

    parser = argparse.ArgumentParser(description="Extract text + metadata from pdf/md/docx.")
    parser.add_argument("path", help="Path to the source .pdf/.md/.docx")
    parser.add_argument("--out", default=None, help="Output dir (default: a temp dir)")
    args = parser.parse_args(argv)

    try:
        result = extract(args.path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except UnsupportedFormatError as exc:
        print(f"Unsupported format: {exc}", file=sys.stderr)
        return 2
    except MissingDependencyError as exc:
        print(str(exc), file=sys.stderr)
        return 3

    out_dir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="book-to-skill-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    full_text = out_dir / "full_text.txt"
    metadata = out_dir / "metadata.json"
    full_text.write_text(result.text, encoding="utf-8")
    metadata.write_text(json.dumps(result.metadata, indent=2, default=str), encoding="utf-8")

    print(str(full_text))
    print(str(metadata))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
