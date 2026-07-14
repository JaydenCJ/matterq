"""End-to-end CLI behavior: subcommands, formats, exit codes."""

import json

import pytest

from matterq import __version__
from matterq.cli import main


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_version_flag_and_bare_invocation(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == f"matterq {__version__}"
    code, out, _ = run(capsys)  # no subcommand: help + exit 2
    assert code == 2
    assert "query" in out


def test_query_table_output(sample_vault, capsys):
    code, out, err = run(
        capsys,
        "query",
        'SELECT title, due FROM "projects" WHERE status = "active" SORT due',
        "--root",
        str(sample_vault),
    )
    assert code == 0
    assert err == ""
    lines = out.strip().split("\n")
    assert lines[0].split() == ["title", "due"]
    assert lines[2].startswith("Beta")  # due 2026-07-20 sorts first
    assert lines[3].startswith("Alpha")


def test_query_json_with_projection(sample_vault, capsys):
    code, out, _ = run(
        capsys,
        "query",
        "SELECT file.name, priority SORT priority LIMIT 1",
        "--root",
        str(sample_vault),
        "--format",
        "json",
    )
    assert code == 0
    assert json.loads(out) == [{"file.name": "alpha", "priority": 1}]


def test_query_json_without_projection_dumps_full_records(sample_vault, capsys):
    code, out, _ = run(
        capsys,
        "query",
        'WHERE file.name = "book"',
        "--root",
        str(sample_vault),
        "--format",
        "json",
    )
    records = json.loads(out)
    assert code == 0
    assert records[0]["file.path"] == "reading/book.md"
    assert records[0]["rating"] == 5
    assert records[0]["tags"] == ["books", "reread"]


def test_query_ndjson_streams_one_line_per_note(sample_vault, capsys):
    code, out, _ = run(
        capsys,
        "query",
        'FROM "projects"',
        "--root",
        str(sample_vault),
        "--format",
        "ndjson",
    )
    lines = out.strip().split("\n")
    assert code == 0
    assert len(lines) == 3
    assert all(
        json.loads(line)["file.path"].startswith("projects/")
        for line in lines
    )


def test_query_paths_format_for_xargs(sample_vault, capsys):
    code, out, _ = run(
        capsys,
        "query",
        'WHERE status = "archived"',
        "--root",
        str(sample_vault),
        "--format",
        "paths",
    )
    assert code == 0
    assert out.strip() == "projects/gamma.md"


def test_query_count_format_including_zero(sample_vault, capsys):
    code, out, _ = run(
        capsys, "query", "", "--root", str(sample_vault), "--format", "count"
    )
    assert (code, out.strip()) == (0, "5")
    code, out, _ = run(
        capsys,
        "query",
        'WHERE status = "nope"',
        "--root",
        str(sample_vault),
        "--format",
        "count",
    )
    assert (code, out.strip()) == (0, "0")


def test_fail_empty_exits_1(sample_vault, capsys):
    code, _, _ = run(
        capsys,
        "query",
        'WHERE status = "nope"',
        "--root",
        str(sample_vault),
        "--fail-empty",
    )
    assert code == 1


def test_bad_query_exits_2_with_message(sample_vault, capsys):
    code, _, err = run(capsys, "query", "WHERE ((", "--root", str(sample_vault))
    assert code == 2
    assert "query error" in err


def test_missing_root_exits_1(capsys, tmp_path):
    code, _, err = run(capsys, "query", "", "--root", str(tmp_path / "missing"))
    assert code == 1
    assert "error" in err


def test_broken_note_warns_on_stderr_but_query_succeeds(make_vault, capsys):
    root = make_vault({"bad.md": '---\nx: "oops\n---\n', "ok.md": "fine"})
    code, out, err = run(
        capsys, "query", "", "--root", str(root), "--format", "paths"
    )
    assert code == 0
    assert out.strip().split("\n") == ["bad.md", "ok.md"]
    assert "warning: bad.md" in err


def test_fields_subcommand_table_and_json(sample_vault, capsys):
    code, out, _ = run(capsys, "fields", "--root", str(sample_vault))
    assert code == 0
    lines = out.strip().split("\n")
    assert lines[0].split() == ["field", "notes", "coverage", "types"]
    assert any(line.startswith("status") and "string" in line for line in lines)
    code, out, _ = run(
        capsys, "fields", "--root", str(sample_vault), "--format", "json"
    )
    records = {r["field"]: r for r in json.loads(out)}
    assert code == 0
    assert records["status"]["notes"] == 4
    assert records["status"]["coverage"] == "80%"
    assert records["rating"]["types"] == "int"


def test_get_subcommand_and_missing_file(sample_vault, capsys, tmp_path):
    code, out, _ = run(capsys, "get", str(sample_vault / "projects/alpha.md"))
    data = json.loads(out)
    assert code == 0
    assert data["fields"]["title"] == "Alpha"
    assert data["fields"]["due"] == "2026-08-01"
    assert data["tags"] == ["work", "web", "q3"]
    code, _, err = run(capsys, "get", str(tmp_path / "absent.md"))
    assert code == 1
    assert "error" in err


def test_get_malformed_front_matter_exits_2(make_vault, capsys):
    root = make_vault({"bad.md": '---\nx: "oops\n---\n'})
    code, _, err = run(capsys, "get", str(root / "bad.md"))
    assert code == 2
    assert "front matter error" in err


def test_no_recursive_flag(sample_vault, capsys):
    code, out, _ = run(
        capsys,
        "query",
        "",
        "--root",
        str(sample_vault),
        "--no-recursive",
        "--format",
        "paths",
    )
    assert code == 0
    assert out.strip() == "inbox.md"
