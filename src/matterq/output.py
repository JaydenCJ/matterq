"""Output rendering: aligned text tables, Markdown, JSON, NDJSON, CSV.

All renderers take the same ``(headers, rows)`` shape produced by
:func:`project`, so a query result can be re-rendered in any format
without re-running the query.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .engine import get_field
from .scanner import Note

__all__ = [
    "FORMATS",
    "format_cell",
    "project",
    "render",
    "to_jsonable",
]

FORMATS = ("table", "md", "json", "ndjson", "csv", "count", "paths")


def to_jsonable(value: Any) -> Any:
    """Convert parsed front-matter values into JSON-serializable ones."""
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    return value


def format_cell(value: Any) -> str:
    """Human-facing cell text for table/md/csv output."""
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    if isinstance(value, list):
        return ", ".join(format_cell(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(to_jsonable(value), sort_keys=True)
    return str(value)


def project(
    notes: Sequence[Note], select: Optional[List[str]]
) -> Tuple[List[str], List[List[Any]]]:
    """Project notes onto columns; default projection is ``file.path``."""
    headers = list(select) if select else ["file.path"]
    rows = [[get_field(note, name) for name in headers] for note in notes]
    return headers, rows


def _widths(headers: List[str], cells: List[List[str]]) -> List[int]:
    widths = [len(h) for h in headers]
    for row in cells:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))
    return widths


def render_table(headers: List[str], rows: List[List[Any]]) -> str:
    """Plain-text table with a dashed underline, columns left-aligned."""
    cells = [[format_cell(value) for value in row] for row in rows]
    widths = _widths(headers, cells)
    lines = [
        "  ".join(h.ljust(w) for h, w in zip(headers, widths)).rstrip(),
        "  ".join("-" * w for w in widths).rstrip(),
    ]
    for row in cells:
        lines.append(
            "  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip()
        )
    return "\n".join(lines)


def render_markdown(headers: List[str], rows: List[List[Any]]) -> str:
    """GitHub-flavored Markdown table (pipes in cells are escaped)."""

    def escape(text: str) -> str:
        return text.replace("|", "\\|")

    lines = [
        "| " + " | ".join(escape(h) for h in headers) + " |",
        "|" + "|".join(" --- " for _ in headers) + "|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(escape(format_cell(value)) for value in row)
            + " |"
        )
    return "\n".join(lines)


def _json_records(
    headers: List[str], rows: List[List[Any]]
) -> List[Dict[str, Any]]:
    return [
        {header: to_jsonable(value) for header, value in zip(headers, row)}
        for row in rows
    ]


def render_json(headers: List[str], rows: List[List[Any]]) -> str:
    return json.dumps(_json_records(headers, rows), indent=2, sort_keys=False)


def render_ndjson(headers: List[str], rows: List[List[Any]]) -> str:
    return "\n".join(
        json.dumps(record, sort_keys=False)
        for record in _json_records(headers, rows)
    )


def render_csv(headers: List[str], rows: List[List[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([format_cell(value) for value in row])
    return buffer.getvalue().rstrip("\n")


def render(fmt: str, headers: List[str], rows: List[List[Any]]) -> str:
    """Render a projected result in one of :data:`FORMATS`."""
    if fmt == "table":
        return render_table(headers, rows)
    if fmt == "md":
        return render_markdown(headers, rows)
    if fmt == "json":
        return render_json(headers, rows)
    if fmt == "ndjson":
        return render_ndjson(headers, rows)
    if fmt == "csv":
        return render_csv(headers, rows)
    if fmt == "count":
        return str(len(rows))
    if fmt == "paths":
        # Always the file path, whatever the projection was.
        raise ValueError("render('paths') needs notes; use render_paths")
    raise ValueError(f"unknown format {fmt!r}")


def render_paths(notes: Sequence[Note]) -> str:
    """One relative path per line — the xargs-friendly format."""
    return "\n".join(note.rel for note in notes)
