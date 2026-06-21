"""CLI tests for build / analyze / extract (offline via the stub provider)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from book_to_skill.cli import main


def test_cli_extract_writes_files(sample_md: Path, tmp_path: Path, capsys):
    out = tmp_path / "ex"
    rc = main(["extract", str(sample_md), "--out", str(out)])
    assert rc == 0
    printed = capsys.readouterr().out.strip().splitlines()
    assert (out / "full_text.txt").is_file()
    assert (out / "metadata.json").is_file()
    assert str(out / "full_text.txt") in printed[0]
    meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    assert meta["format"] == "md"
    assert "chapter_spans" in meta


def test_cli_analyze_prints_report(sample_md: Path, capsys):
    rc = main(["analyze", str(sample_md)])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["chapters_detected"] >= 3
    assert "signal_counts" in report


def test_cli_build_with_stub(sample_md: Path, tmp_path: Path, capsys):
    skills = tmp_path / "skills"
    rc = main(
        [
            "build",
            str(sample_md),
            "demo",
            "--provider",
            "stub",
            "--yes",
            "--skills-root",
            str(skills),
        ]
    )
    assert rc == 0
    assert (skills / "demo" / "SKILL.md").is_file()
    out = capsys.readouterr().out
    assert "Pre-flight" in out
    assert "Done." in out


def test_cli_build_analyze_only(sample_md: Path, capsys):
    rc = main(["build", str(sample_md), "--analyze-only"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["format"] == "md"


def test_cli_missing_provider_errors(sample_md: Path, monkeypatch, capsys):
    monkeypatch.delenv("BOOK_TO_SKILL_PROVIDER", raising=False)
    rc = main(["build", str(sample_md), "--yes"])
    assert rc == 2
    assert "provider" in capsys.readouterr().err.lower()


def test_cli_unsupported_format(tmp_path: Path, capsys):
    blob = tmp_path / "thing.bin"
    blob.write_bytes(b"\x00\x01\x02\x03\xff\xfe\x89PNG")
    rc = main(["extract", str(blob)])
    assert rc == 2
    assert "unsupported" in capsys.readouterr().err.lower()


def test_cli_missing_file(capsys):
    rc = main(["analyze", "no-such-file.md"])
    assert rc == 2
    assert "error" in capsys.readouterr().err.lower()


def test_cli_requires_subcommand(capsys):
    with pytest.raises(SystemExit):
        main([])
