"""book-to-skill CLI: build / analyze / extract."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from book_to_skill import __version__
from book_to_skill.config import (
    ConfigError,
    build_provider,
    default_model_for,
    estimate_cost,
    select_provider_name,
)
from book_to_skill.extract import MissingDependencyError, UnsupportedFormatError, extract
from book_to_skill.generate import analyze_only, generate_skill


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def _cmd_extract(args: argparse.Namespace) -> int:
    res = extract(args.path)
    out_dir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="book-to-skill-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    full_text = out_dir / "full_text.txt"
    metadata = out_dir / "metadata.json"
    full_text.write_text(res.text, encoding="utf-8")
    metadata.write_text(json.dumps(res.metadata, indent=2, default=str), encoding="utf-8")
    print(str(full_text))
    print(str(metadata))
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    report = analyze_only(args.path)
    print(json.dumps(report, indent=2, default=str))
    return 0


def _print_cost_preflight(res, model: str | None) -> None:
    meta = res.metadata
    in_tokens = int(meta.get("estimated_tokens", 0))
    n_chapters = len(meta.get("chapter_spans") or [])
    # Rough output estimate: ~1200 tokens/chapter + ~8500 for the 4 aggregate files.
    out_tokens = n_chapters * 1200 + 8500
    pages = meta.get("page_count") or meta.get("paragraph_count") or n_chapters
    print(
        f"Pre-flight: ~{pages} pages/sections, {meta.get('words', 0)} words, "
        f"~{in_tokens} input tokens, ~{n_chapters} chapters."
    )
    cost = estimate_cost(model, in_tokens, out_tokens)
    if cost is not None:
        print(f"Estimated cost for model '{model}': ~${cost} (verify current provider pricing).")
    else:
        print(f"No price on file for model '{model}'; skipping cost estimate (verify pricing).")


def _cmd_build(args: argparse.Namespace) -> int:
    res = extract(args.path)

    if args.analyze_only:
        report = analyze_only(args.path)
        print(json.dumps(report, indent=2, default=str))
        return 0

    name = select_provider_name(args.provider)
    model = args.model or default_model_for(name)
    _print_cost_preflight(res, model)

    if not args.yes and sys.stdin.isatty():
        try:
            answer = input("Proceed with generation? [y/N] ").strip().lower()
        except EOFError:
            answer = "n"
        if answer not in {"y", "yes"}:
            print("Aborted.")
            return 1

    provider = build_provider(name, model=args.model, base_url=args.base_url)
    skills_root = Path(args.skills_root) if args.skills_root else None
    result = generate_skill(
        extract_result=res,
        provider=provider,
        style=args.style,
        slug=args.slug,
        skills_root=skills_root,
        on_log=print,
    )
    print(f"Done. Skill written to: {result['skill_dir']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="book-to-skill",
        description="Turn a PDF/MD/DOCX book into a Claude Code skill.",
    )
    parser.add_argument("--version", action="version", version=f"book-to-skill {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Extract and generate a skill (API mode).")
    p_build.add_argument("path", help="Path to the source .pdf/.md/.docx")
    p_build.add_argument("slug", nargs="?", default=None, help="Optional skill slug")
    p_build.add_argument(
        "--provider", default=None, help="Provider name (or BOOK_TO_SKILL_PROVIDER)"
    )
    p_build.add_argument("--model", default=None, help="Model id (defaults to provider preset)")
    p_build.add_argument("--base-url", default=None, help="Override base URL (for local/custom)")
    p_build.add_argument(
        "--style",
        choices=["technical", "prose", "auto"],
        default="auto",
        help="Summarization style",
    )
    p_build.add_argument(
        "--analyze-only", action="store_true", help="Only print an analysis report"
    )
    p_build.add_argument("--skills-root", default=None, help="Override ~/.claude/skills root")
    p_build.add_argument("--yes", "-y", action="store_true", help="Skip the confirmation prompt")
    p_build.set_defaults(func=_cmd_build)

    p_analyze = sub.add_parser("analyze", help="Print an extraction/structure report only.")
    p_analyze.add_argument("path", help="Path to the source .pdf/.md/.docx")
    p_analyze.set_defaults(func=_cmd_analyze)

    p_extract = sub.add_parser(
        "extract", help="Extract text; write full_text.txt + metadata.json (skill-mode helper)."
    )
    p_extract.add_argument("path", help="Path to the source .pdf/.md/.docx")
    p_extract.add_argument("--out", default=None, help="Output dir (default: a temp dir)")
    p_extract.set_defaults(func=_cmd_extract)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        _eprint(f"Error: {exc}")
        return 2
    except UnsupportedFormatError as exc:
        _eprint(f"Unsupported format: {exc}")
        return 2
    except MissingDependencyError as exc:
        _eprint(str(exc))
        return 3
    except ConfigError as exc:
        _eprint(f"Configuration error: {exc}")
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
