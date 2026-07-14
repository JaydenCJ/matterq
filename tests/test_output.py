"""Rendering: table alignment, Markdown escaping, JSON/CSV fidelity."""

import csv
import datetime
import io
import json

from matterq.output import (
    format_cell,
    project,
    render,
    render_paths,
    to_jsonable,
)
from matterq.scanner import Note


def note(rel, **fields):
    return Note(path=None, rel=rel, fields=fields)


NOTES = [
    note("a.md", title="Alpha", due=datetime.date(2026, 8, 1), n=1),
    note("b.md", title="Beta | pipe", n=2),
]


def test_default_projection_is_file_path():
    headers, rows = project(NOTES, None)
    assert headers == ["file.path"]
    assert rows == [["a.md"], ["b.md"]]


def test_table_columns_aligned_without_trailing_whitespace():
    headers, rows = project(NOTES, ["title", "due"])
    lines = render("table", headers, rows).split("\n")
    assert lines[0].startswith("title")
    assert set(lines[1]) <= {"-", " "}
    # Every "due" cell starts at the same column as the header.
    col = lines[0].index("due")
    assert lines[2][col:].startswith("2026-08-01")
    assert all(line == line.rstrip() for line in lines)


def test_markdown_table_escapes_pipes():
    headers, rows = project(NOTES, ["title"])
    text = render("md", headers, rows)
    assert "| Beta \\| pipe |" in text
    assert text.split("\n")[1] == "| --- |"


def test_json_and_ndjson_serialize_dates_as_iso():
    headers, rows = project(NOTES, ["title", "due"])
    records = json.loads(render("json", headers, rows))
    assert records[0] == {"title": "Alpha", "due": "2026-08-01"}
    assert records[1]["due"] is None
    lines = render("ndjson", headers, rows).split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"title": "Alpha", "due": "2026-08-01"}


def test_csv_round_trips_through_csv_reader():
    headers, rows = project(NOTES, ["title", "n"])
    parsed = list(csv.reader(io.StringIO(render("csv", headers, rows))))
    assert parsed == [["title", "n"], ["Alpha", "1"], ["Beta | pipe", "2"]]


def test_count_and_paths_formats():
    headers, rows = project(NOTES, None)
    assert render("count", headers, rows) == "2"
    assert render_paths(NOTES) == "a.md\nb.md"


def test_cell_formatting_for_every_value_type():
    assert format_cell(None) == ""
    assert format_cell(True) == "true"
    assert format_cell(False) == "false"
    assert format_cell(2.0) == "2"
    assert format_cell(2.5) == "2.5"
    assert format_cell(datetime.date(2026, 1, 2)) == "2026-01-02"
    assert format_cell(["a", "b", 3]) == "a, b, 3"
    assert format_cell({"b": 1, "a": datetime.date(2026, 1, 1)}) == (
        '{"a": "2026-01-01", "b": 1}'
    )
    assert to_jsonable(
        {"when": [datetime.datetime(2026, 1, 1, 8, 0)], "n": 1}
    ) == {"when": ["2026-01-01T08:00:00"], "n": 1}
