---
name: book-to-skill
description: Turn a technical book or document (PDF, Markdown, or DOCX) into a reusable Claude Code skill — a front-loaded SKILL.md plus on-demand chapter summaries, glossary, patterns, and a cheatsheet. Use when the user wants to "make a skill from this book/PDF/doc", distill a reference into something you can consult while coding, or build a knowledge skill from a long document.
when_to_use: make a skill from this book; turn this PDF into a skill; book to skill; distill this document into a skill; create a Claude skill from <file>; summarize this book into a reusable skill; build a knowledge skill from this DOCX
disable-model-invocation: true
context: fork
agent: general-purpose
allowed-tools: Read Write Glob Grep Bash(python3 *) Bash(mkdir *) Bash(cp *) Bash(find *) Bash(wc *) Bash(cat *) Bash(date *) Bash(rm *) Bash(book-to-skill *)
argument-hint: <path-to-pdf|md|docx> [skill-name-slug]
arguments: [source_path, skill_name]
---

# book-to-skill (skill mode)

Convert the document at `$0` (alias `$ARGUMENTS[0]`) into a Claude Code skill installed
under `~/.claude/skills/<slug>/`. The optional second argument `$1` is the skill slug.
If no arguments were substituted, use the values in `ARGUMENTS:` appended below.

You (the agent) do the synthesis by reading the extracted text. Our Python code only
**extracts** text and metadata — it does not call any model in skill mode.

## 0. Out-of-scope check

If `$0` is not a path to a `.pdf`, `.md`/`.markdown`, or `.docx` file, stop and tell the
user the only supported inputs are PDF, Markdown, and DOCX. Do not attempt other formats.

## 1. Decide the mode

- **Full build** (default): extract → analyze → generate all 5 file types.
- **Analyze-only**: if the user said "analyze" / "just tell me what's in it", run steps 2–4
  and report; write nothing.
- **Generate-from-analysis**: if an analysis already exists in this session, skip re-extraction
  and go straight to step 5.

If `--provider` was given or `BOOK_TO_SKILL_PROVIDER` is set in the environment, do **API mode**
instead: shell out and report its result, then stop:

```bash
book-to-skill build "$0" "$1" --provider "$BOOK_TO_SKILL_PROVIDER" --yes
```

## 2. Validate input and extract

Run the extractor (works regardless of the current directory):

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/extract.py" "$0"
```

It prints two paths: a `full_text.txt` and a `metadata.json` in a temp directory. Remember both.

## 3. Read the metadata

`cat` the `metadata.json`. Note: `format`, `method`, `words`, `estimated_tokens`,
`page_count`/`paragraph_count`, `has_toc`, `chapters_detected`, `structure_fallback`, and
`chapter_spans` (each is `[start_char, end_char, title]`). If `structure_fallback` is true,
the document had no detectable chapters and was split into evenly-sized sections — treat each
"Section N" as a chapter.

## 4. Cost pre-flight + structure analysis

Skill mode makes **no** model API calls, so the direct cost is $0. Still, briefly report scale
(pages/words/estimated tokens, chapter count). If you later use API mode, prices are config-driven
in `src/book_to_skill/config.py` (`MODEL_PRICES`) — verify current pricing at
<https://docs.claude.com/en/docs/about-claude/pricing> and each provider's pricing page.

Read `full_text.txt` (or the relevant `chapter_spans` slices). Identify the core mental models,
frameworks, techniques, and any anti-patterns.

## 5. Ask one question, then choose a slug

Ask the user a single question: **what they will use this skill for** (and whether to bias toward
`technical` fidelity or `prose` voice). Then determine the slug:

- If `$1` is set, use it.
- Otherwise propose `{author-lastname}-{core-concept}` when the book has a strong methodological
  identity, else a title-based slug.

Collision rule: if `~/.claude/skills/<slug>/` already exists, **ask the user** before doing
anything, or append `-2` (then `-3`, …). Never silently overwrite.

## 6. Create the directory tree

```bash
mkdir -p ~/.claude/skills/<slug>/chapters
```

## 7. Generate the files

Write each file by synthesizing from the extracted text. Keep the token budgets:

- `chapters/chNN-<short-title>.md` — one dense summary per chapter (~800–1,200 tokens). Use
  `chapter_spans` to slice `full_text.txt`. Number them `ch01`, `ch02`, … Most important content first.
- `glossary.md` — key terms, alphabetical, with chapter refs (~1.5k tokens).
- `patterns.md` — techniques / algorithms / design patterns (~2k tokens).
- `cheatsheet.md` — decision tables + quick rules (~1k tokens).
- `SKILL.md` — the master file (~4k tokens body, **most important content first** because
  compaction truncates from the end). It must contain:
  - YAML frontmatter with `name`, `description`, `when_to_use` (10–15 trigger phrases),
    `allowed-tools: Read Grep`, and `argument-hint`.
  - The core mental models.
  - A **Chapter Index** with links like `[Title](chapters/ch01-title.md)` — every link must resolve.
  - A **Topic Index** mapping topics to the chapters that cover them.

## 8. Cleanup

Remove the temp extraction directory printed in step 2:

```bash
rm -rf "<temp-dir-from-step-2>"
```

## 9. Report

Tell the user the installed path, the slug, the number of chapter files, and how to invoke the
new skill (`/<slug>` or by asking Claude about the book's topics).
