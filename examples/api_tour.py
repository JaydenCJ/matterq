"""The matterq Python API in a dozen lines.

Scan a vault, run a query, and render the result — the same pipeline
the CLI uses, importable from any script.
"""

from pathlib import Path

from matterq import apply_query, parse_query, scan
from matterq.output import project, render

VAULT = Path(__file__).parent / "vault"

notes, warnings = scan(VAULT)
print(f"scanned {len(notes)} notes, {len(warnings)} warnings")

query = parse_query(
    'SELECT title, status, due FROM "projects" '
    'WHERE status = "active" SORT due ASC'
)
result = apply_query(notes, query)

headers, rows = project(result, query.select)
print(render("table", headers, rows))

# Individual notes are plain data: .rel, .fields (dict), .tags (list).
soonest = result[0]
print(f"\nnext due: {soonest.fields['due']} -> {soonest.rel}")
