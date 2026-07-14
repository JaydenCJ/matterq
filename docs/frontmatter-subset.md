# The matterq front-matter subset

matterq parses front matter with its own zero-dependency parser rather
than a YAML library. It implements the subset of YAML that appears in
real Markdown vaults, with YAML 1.2 scalar semantics. This page is the
contract: everything listed here is supported and tested; anything not
listed is out of scope for 0.1.0.

## Document shape

Front matter is the block between an opening `---` on the **first
line** of the file and the next `---` (or `...`) line. A `---` with no
closing fence is treated as a horizontal rule, i.e. the file has no
front matter. A UTF-8 BOM before the opening fence is ignored. CRLF
line endings work. A file without front matter is still a valid note —
it just has no fields beyond `file.*` and inline tags.

## Scalars

| Input | Parsed as |
|---|---|
| `hello world`, `"a # b"`, `'it''s'` | string (plain, double-quoted, single-quoted) |
| `42`, `-7` | int |
| `3.14`, `1e3` | float |
| `true`, `False`, `TRUE` | bool |
| `null`, `~`, empty | null |
| `2026-07-31` | date |
| `2026-07-31T09:30`, `2026-07-31 09:30:15` | datetime |
| `yes`, `no`, `on`, `off` | **string** (YAML 1.2: no Norway problem) |
| `2026-13-40`, `1.2.3` | string (date-lookalikes fall back safely) |

In double-quoted strings `\n`, `\t`, `\r`, `\"`, `\\`, and `\0` are
escapes. In single-quoted strings `''` is a literal apostrophe.

## Collections

- Flow lists and maps, nested arbitrarily: `[a, b]`, `{k: v}`,
  `[{name: a}, {name: b}]`. Plain scalars inside flow collections may
  not contain `,`, `:`, `]`, or `}` — quote them.
- Block lists, indented or at the key's own indent, with typed items
  and compact single-pair mapping items (`- name: build`).
- Nested block mappings by indentation (spaces only; a tab in
  indentation is an error with a line number).

## Block scalars

`|` (literal) preserves line breaks and relative indentation; `>`
(folded) joins lines with spaces and turns blank lines into paragraph
breaks. Chomping indicators (`|-`, `>+`, ...) are accepted and treated
like the plain style: trailing blank lines are dropped.

## Comments and edge cases

- `# comment` lines and trailing comments are stripped; a `#` needs a
  preceding space to start a comment, so `news#general` is a value and
  `"a # b"` stays intact.
- Values may contain colons (`title: Meeting: next steps`, URLs).
- Duplicate keys: last one wins (lenient by design — Obsidian-style
  vaults contain these).
- Keys may be quoted to contain special characters: `"weird key": 1`.

## Not supported (0.1.0)

Anchors/aliases (`&`, `*`), explicit tags (`!!str`), multi-document
streams, flow collections spanning multiple lines, and nested block
structures inside list items. Files using these parse as far as
possible; on a hard error the note is kept with empty fields and the
CLI prints a warning to stderr instead of failing the whole query.
