# The matterq query language

A query is a single string of up to five clauses, **in this order**,
every one of them optional (an empty query matches every note):

```
SELECT <field>, ...  |  SELECT *
FROM   "folder" | #tag   (comma-separated; sources combine as OR)
WHERE  <expression>
SORT   <field> [ASC|DESC], ...
LIMIT  <n>
```

Keywords are case-insensitive; field names are not.

## Fields

Any front-matter key is a field. Dotted names descend into nested
mappings (`owner.team`). Field names with spaces can be quoted in
`SELECT` and `SORT` (`SELECT "read on"`).

Implicit fields, available on every note:

| Field | Meaning | Example |
|---|---|---|
| `file.path` | Path relative to the vault root (POSIX slashes) | `projects/alpha.md` |
| `file.name` | File name without extension | `alpha` |
| `file.folder` | Containing folder (`""` at the root) | `projects` |
| `file.ext` | Extension without the dot | `md` |
| `file.size` | File size in bytes | `412` |
| `tags` | Front-matter tags merged with inline `#tags` from the body | `[work, q3]` |

## Literals

Strings (`"..."` or `'...'`), integers, floats, `true`, `false`,
`null`, bare dates (`2026-07-31`), bare datetimes (`2026-07-31T09:30`),
and lists of literals (`["open", "blocked"]`). In double-quoted strings
`\n`, `\t`, `\"`, and `\\` are escapes; anything else keeps its
backslash, so `"^\d{4}"` works as a regex.

## Operators

| Operator | Meaning |
|---|---|
| `=` / `==`, `!=` | Equality. Type-strict: `true != 1`, a date never equals its string form |
| `<` `<=` `>` `>=` | Ordering. Defined within a type family (numbers, strings, dates); comparing across families is `false`, never an error |
| `CONTAINS` | List membership, substring, or map-key test, by the left side's type |
| `IN` | Reverse of `CONTAINS`: `status IN ["open", "blocked"]` |
| `MATCHES` | Regular-expression search on strings (Python `re` syntax) |
| `AND`, `OR`, `NOT` | Boolean logic; `AND` binds tighter, parentheses override |

A bare field in boolean position tests truthiness: `WHERE due` keeps
notes that have a non-empty `due`. `null`, `false`, `""`, `[]`, and
`{}` are falsy; note that `0` is truthy — it is a real value.

A bare `#tag` in `WHERE` is shorthand for `tags CONTAINS "tag"`.

## Missing values

A missing field evaluates to `null`. `field = null` is therefore the
idiom for "field absent", and any ordered comparison against a missing
field is `false`. In `SORT`, `null` always goes last — in both
directions — so ascending "next due date" queries are not drowned in
undated notes.

## Sorting rules

Sorting never raises on mixed types. Values order by type family
first (booleans, numbers, dates, strings, lists/maps), then within the
family: numerically, chronologically, or case-insensitively for
strings. Ties break on `file.path`, so a query's output order is fully
deterministic for a given vault.

## Sources (`FROM`)

`FROM "projects"` keeps notes under that folder (path-segment safe:
`"proj"` does not match `projects/`). `FROM #books` keeps notes
carrying the tag, case-insensitively, whether the tag came from front
matter or the note body. Multiple sources combine as OR; combine with
`WHERE` for AND semantics.
