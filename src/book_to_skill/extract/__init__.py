"""Extraction subpackage: route a source file to the right extractor."""

from book_to_skill.extract.router import (
    ExtractResult,
    MissingDependencyError,
    UnsupportedFormatError,
    extract,
)

__all__ = [
    "ExtractResult",
    "MissingDependencyError",
    "UnsupportedFormatError",
    "extract",
]
