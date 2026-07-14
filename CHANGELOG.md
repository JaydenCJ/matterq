# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-13

### Added

- Dependency-free front-matter parser implementing a documented YAML
  subset (`docs/frontmatter-subset.md`): typed scalars with YAML 1.2
  semantics (no Norway problem), dates and datetimes as real objects,
  flow lists/maps, block lists, nested mappings, `|`/`>` block scalars,
  comments, quoted keys, CRLF and BOM handling.
- Vault scanner: recursive Markdown discovery with deterministic
  path-sorted output, dot-directory skipping (`.obsidian`, `.git`),
  inline `#tag` extraction that ignores code fences and code spans, and
  front-matter/body tag merging with case-insensitive deduplication.
  Malformed notes degrade to a stderr warning, never a crash.
- Query language (`docs/query-language.md`): `SELECT` / `FROM`
  (folders and `#tags`, OR-combined) / `WHERE` / `SORT` / `LIMIT`;
  operators `=` `!=` `<` `<=` `>` `>=` `CONTAINS` `IN` `MATCHES`,
  boolean `AND`/`OR`/`NOT` with parentheses, date literals, list
  literals, and bare-field truthiness.
- Evaluation semantics built for messy vaults: missing fields are
  `null`, cross-type ordered comparisons are `false` instead of errors,
  and `null` sorts last in both directions with a `file.path`
  tiebreaker for fully deterministic output.
- Implicit `file.path` / `file.name` / `file.folder` / `file.ext` /
  `file.size` metadata fields and dotted access into nested mappings.
- `matterq` CLI: `query` (formats: `table`, `md`, `json`, `ndjson`,
  `csv`, `count`, `paths`), `fields` (front-matter inventory with
  coverage and types), `get` (one file as JSON); `--fail-empty` for CI
  gates, exit codes 0/1/2, and graceful `SIGPIPE`/`head` handling.
- Python API mirroring the CLI pipeline: `scan`, `parse_query`,
  `apply_query`, plus renderers in `matterq.output`.
- Runnable example vault and API tour under `examples/`.
- 92 offline deterministic tests and `scripts/smoke.sh`.

### Notes

- The repository ships no CI workflow; verification is local —
  `pip install -e '.[dev]' && pytest && bash scripts/smoke.sh`.

[0.1.0]: https://github.com/JaydenCJ/matterq/releases/tag/v0.1.0
