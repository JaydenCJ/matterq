# Contributing to matterq

Thanks for your interest in contributing. Issues, discussions, and pull
requests are all welcome.

## Development setup

```bash
git clone https://github.com/JaydenCJ/matterq
cd matterq
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running the checks

```bash
pytest                 # 92 unit + CLI tests, all offline
bash scripts/smoke.sh  # end-to-end: real queries against the example vault
```

Both must pass before a pull request is reviewed; the smoke script must
print `SMOKE OK`. The whole suite runs fully offline in about a second.

## Ground rules

- **No runtime dependencies, ever.** The front-matter parser existing
  instead of PyYAML is the point of the project. Test-only dependencies
  belong in the `dev` extra.
- **Language changes need docs and tests together.** Anything that
  changes query semantics must update `docs/query-language.md`, and any
  front-matter behavior change must update
  `docs/frontmatter-subset.md`, in the same pull request.
- **Never crash on user notes.** A malformed file becomes a warning on
  stderr, not a traceback; regressions here are release blockers.
- **Determinism is a feature.** Output order must be reproducible for a
  given vault: no wall-clock, no filesystem-order, no locale
  dependence. Tests use `tmp_path` fixtures only.
- **Keep the three READMEs aligned.** `README.md`, `README.zh.md`, and
  `README.ja.md` share the same structure; update all three when you
  change one (English is the authoritative version).
- Code comments and doc comments are written in English.

## Reporting bugs

Please include the query, the output of `matterq --version`, and a
minimal note file that reproduces the problem — front matter is usually
short enough to paste inline. For parser issues, the exact error line
from `matterq: warning: ...` is enough to locate the case.

## Security

matterq reads local files and never makes network calls. If you find
something security-relevant anyway (e.g. a path-traversal issue),
please use GitHub's private vulnerability reporting instead of a
public issue.
