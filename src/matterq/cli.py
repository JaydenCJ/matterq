"""The matterq command-line interface.

Subcommands:

* ``matterq query "<query>"`` — run a query, print table/JSON/CSV/...
* ``matterq fields``          — inventory of front-matter fields
* ``matterq get <file>``      — parsed front matter of one file, as JSON

Exit codes: 0 success, 1 empty result with ``--fail-empty`` or an I/O
problem, 2 malformed query / front matter passed to ``get``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .engine import apply_query
from .inventory import field_stats
from .output import (
    FORMATS,
    project,
    render,
    render_paths,
    render_table,
    to_jsonable,
)
from .query import QueryError, parse_query
from .scanner import read_note, scan

__all__ = ["main"]

_EXIT_OK = 0
_EXIT_IO = 1
_EXIT_USAGE = 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="matterq",
        description="Query a folder of Markdown by front matter.",
    )
    parser.add_argument(
        "--version", action="version", version=f"matterq {__version__}"
    )
    sub = parser.add_subparsers(dest="command")

    query = sub.add_parser(
        "query", help="run a query against a vault of Markdown files"
    )
    query.add_argument(
        "text",
        metavar="QUERY",
        help='e.g. \'SELECT title, due WHERE status = "open" SORT due\'',
    )
    query.add_argument(
        "--root",
        default=".",
        metavar="DIR",
        help="vault root to scan (default: current directory)",
    )
    query.add_argument(
        "--format",
        choices=FORMATS,
        default="table",
        help="output format (default: table)",
    )
    query.add_argument(
        "--fail-empty",
        action="store_true",
        help="exit 1 when the query returns no notes (for CI gates)",
    )
    query.add_argument(
        "--no-recursive",
        action="store_true",
        help="scan only the top level of the vault",
    )

    fields = sub.add_parser(
        "fields", help="list every front-matter field used in a vault"
    )
    fields.add_argument(
        "--root",
        default=".",
        metavar="DIR",
        help="vault root to scan (default: current directory)",
    )
    fields.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="output format (default: table)",
    )

    get = sub.add_parser(
        "get", help="print one file's parsed front matter as JSON"
    )
    get.add_argument(
        "file", metavar="FILE", help="path to a single Markdown file"
    )
    return parser


def _emit_warnings(warnings: List[str]) -> None:
    for warning in warnings:
        print(f"matterq: warning: {warning}", file=sys.stderr)


def _cmd_query(args: argparse.Namespace) -> int:
    try:
        parsed = parse_query(args.text)
    except QueryError as exc:
        print(f"matterq: query error: {exc}", file=sys.stderr)
        return _EXIT_USAGE
    try:
        notes, warnings = scan(
            Path(args.root), recursive=not args.no_recursive
        )
    except (NotADirectoryError, OSError) as exc:
        print(f"matterq: error: {exc}", file=sys.stderr)
        return _EXIT_IO
    _emit_warnings(warnings)
    try:
        result = apply_query(notes, parsed)
    except QueryError as exc:  # e.g. invalid regex in MATCHES
        print(f"matterq: query error: {exc}", file=sys.stderr)
        return _EXIT_USAGE
    if args.format == "paths":
        text = render_paths(result)
    elif parsed.select is None and args.format in ("json", "ndjson"):
        # No projection: JSON formats dump the full record per note.
        records = [
            {"file.path": note.rel, **to_jsonable(note.fields)}
            for note in result
        ]
        if args.format == "json":
            text = json.dumps(records, indent=2)
        else:
            text = "\n".join(json.dumps(record) for record in records)
    else:
        headers, rows = project(result, parsed.select)
        text = render(args.format, headers, rows)
    if text:
        print(text)
    if args.fail_empty and not result:
        return _EXIT_IO
    return _EXIT_OK


def _cmd_fields(args: argparse.Namespace) -> int:
    try:
        notes, warnings = scan(Path(args.root))
    except (NotADirectoryError, OSError) as exc:
        print(f"matterq: error: {exc}", file=sys.stderr)
        return _EXIT_IO
    _emit_warnings(warnings)
    stats = field_stats(notes)
    if args.format == "json":
        print(json.dumps(stats, indent=2))
        return _EXIT_OK
    headers = ["field", "notes", "coverage", "types"]
    rows = [[record[h] for h in headers] for record in stats]
    print(render_table(headers, rows))
    return _EXIT_OK


def _cmd_get(args: argparse.Namespace) -> int:
    path = Path(args.file)
    try:
        note = read_note(path, path.name)
    except OSError as exc:
        print(f"matterq: error: {exc}", file=sys.stderr)
        return _EXIT_IO
    if note.error:
        print(f"matterq: front matter error: {note.error}", file=sys.stderr)
        return _EXIT_USAGE
    print(
        json.dumps(
            {
                "path": args.file,
                "tags": note.tags,
                "fields": to_jsonable(note.fields),
            },
            indent=2,
        )
    )
    return _EXIT_OK


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return _EXIT_USAGE
    try:
        if args.command == "query":
            return _cmd_query(args)
        if args.command == "fields":
            return _cmd_fields(args)
        return _cmd_get(args)
    except BrokenPipeError:
        # Downstream closed early (e.g. `matterq query ... | head`); that
        # is normal shell usage, not an error worth a traceback.
        try:
            sys.stdout.close()
        except OSError:
            pass
        return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
