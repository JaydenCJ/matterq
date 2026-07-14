# matterq examples

`vault/` is a tiny but realistic notes folder: three projects, two
book notes, a journal entry, and an unfiled inbox note — front-matter
tags, inline `#tags`, nested mappings, dates, and one note with no
front matter at all.

Run everything below from this `examples/` directory. If you have not
installed the package, replace `matterq` with
`PYTHONPATH=../src python3 -m matterq`.

```bash
# Active projects by due date
matterq query 'SELECT title, status, due FROM "projects" WHERE status = "active" SORT due ASC' --root vault

# Books rated 4+, as a Markdown table (paste into a note)
matterq query 'SELECT title, rating FROM #books WHERE rating >= 4 SORT rating DESC' --root vault --format md

# What is due this month, as JSON for a script
matterq query 'SELECT title, due WHERE due <= 2026-07-31' --root vault --format json

# What can I query at all?
matterq fields --root vault

# CI gate: fail if anything is overdue (count must be zero)
test "$(matterq query 'WHERE due AND due < 2026-07-13' --root vault --format count)" = 0

# CI gate the other way round: fail if a required note is missing
matterq query 'WHERE file.name = "inbox"' --root vault --fail-empty --format paths
```

`api_tour.py` shows the same pipeline through the Python API —
scan, parse, apply, render — in a dozen lines:

```bash
PYTHONPATH=../src python3 api_tour.py
```
