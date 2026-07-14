#!/usr/bin/env bash
# Smoke test for matterq: run real queries against the bundled example
# vault and a freshly generated one, in every output format, checking
# exit codes along the way.
# Self-contained: pure stdlib, no network, idempotent (works from a clean tree).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

# Zero runtime dependencies, so running from src/ needs no install.
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

VAULT="$ROOT/examples/vault"
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/matterq-smoke.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

fail() { echo "SMOKE FAIL: $1" >&2; exit 1; }

echo "[smoke] python: $("$PYTHON" --version 2>&1)"

# 1. --version agrees with the package version.
version_out="$("$PYTHON" -m matterq --version)"
pkg_version="$("$PYTHON" -c 'import matterq; print(matterq.__version__)')"
[ "$version_out" = "matterq $pkg_version" ] \
  || fail "--version mismatch: '$version_out' vs package '$pkg_version'"

# 2. A full query pipeline: SELECT + FROM + WHERE + SORT as a table.
table_out="$("$PYTHON" -m matterq query \
  'SELECT title, status, due FROM "projects" WHERE status = "active" SORT due ASC' \
  --root "$VAULT")"
echo "$table_out" | sed 's/^/[table] /'
echo "$table_out" | head -1 | grep -q "title" || fail "table missing header"
[ "$(echo "$table_out" | sed -n '3p' | grep -c 'API migration')" -eq 1 ] \
  || fail "expected API migration first (earliest due date)"
echo "$table_out" | grep -q "Old blog" && fail "archived note leaked through WHERE"

# 3. JSON output is valid and correctly typed (date -> ISO string, int stays int).
"$PYTHON" -m matterq query 'SELECT title, priority, due FROM "projects" SORT priority' \
  --root "$VAULT" --format json > "$WORKDIR/projects.json"
"$PYTHON" - "$WORKDIR/projects.json" <<'EOF' || fail "JSON output failed validation"
import json, sys
rows = json.load(open(sys.argv[1]))
assert len(rows) == 3, rows
assert rows[0] == {"title": "Website redesign", "priority": 1, "due": "2026-08-01"}, rows[0]
EOF

# 4. Tag sources: FROM #books picks up front-matter tags across folders.
books="$("$PYTHON" -m matterq query 'SELECT title, rating FROM #books SORT rating DESC' \
  --root "$VAULT" --format csv)"
echo "$books" | sed 's/^/[csv] /'
echo "$books" | sed -n '2p' | grep -q '^Designing Data-Intensive Applications,5$' \
  || fail "FROM #books did not rank rating 5 first"

# 5. Inline body tags merge with front-matter tags (#deadline only in body).
deadline="$("$PYTHON" -m matterq query 'WHERE #deadline' --root "$VAULT" --format paths)"
[ "$deadline" = "projects/api-migration.md" ] \
  || fail "inline #deadline tag not found: '$deadline'"

# 6. fields inventory sees nested (dotted) keys.
fields_out="$("$PYTHON" -m matterq fields --root "$VAULT")"
echo "$fields_out" | grep -q "owner.team" || fail "fields missing dotted owner.team"

# 7. get prints one file's parsed front matter as JSON.
get_out="$("$PYTHON" -m matterq get "$VAULT/reading/designing-data.md")"
echo "$get_out" | grep -q '"rating": 5' || fail "get did not show rating"

# 8. A fresh vault written on the fly: dates compare as dates, count format works.
mkdir -p "$WORKDIR/vault/todo"
cat > "$WORKDIR/vault/todo/one.md" <<'EOF'
---
title: Renew certificate
due: 2026-07-15
tags: [ops]
---
Renew before it lapses.
EOF
cat > "$WORKDIR/vault/todo/two.md" <<'EOF'
---
title: Quarterly review
due: 2026-10-01
tags: [ops]
---
Not urgent yet.
EOF
overdue="$("$PYTHON" -m matterq query 'WHERE due <= 2026-08-31' \
  --root "$WORKDIR/vault" --format count)"
[ "$overdue" = "1" ] || fail "date comparison count expected 1, got '$overdue'"

# 9. Exit codes: 2 for a malformed query, 1 for --fail-empty with no rows.
set +e
"$PYTHON" -m matterq query 'WHERE ((' --root "$VAULT" >/dev/null 2>&1
[ $? -eq 2 ] || { set -e; fail "malformed query should exit 2"; }
"$PYTHON" -m matterq query 'WHERE title = "does not exist"' \
  --root "$VAULT" --fail-empty >/dev/null 2>&1
[ $? -eq 1 ] || { set -e; fail "--fail-empty should exit 1 on empty result"; }
set -e

echo "SMOKE OK"
