"""Expression semantics against notes: operators, coercions, file.* fields."""

import datetime

import pytest

from matterq.engine import apply_query, evaluate, get_field, matches, truthy
from matterq.query import QueryError, parse_query
from matterq.scanner import Note


def note(fields=None, rel="dir/note.md", tags=None, size=100):
    return Note(
        path=None,
        rel=rel,
        fields=dict(fields or {}),
        tags=list(tags or []),
        size=size,
    )


def where(text):
    return parse_query(f"WHERE {text}").where


def test_get_field_dotted_paths_and_missing():
    n = note({"owner": {"name": "alice", "meta": {"level": 2}}})
    assert get_field(n, "owner.name") == "alice"
    assert get_field(n, "owner.meta.level") == 2
    assert get_field(n, "absent") is None
    assert get_field(n, "owner.name.deeper") is None


def test_file_metadata_fields():
    n = note(rel="projects/deep/alpha.md", size=42)
    assert get_field(n, "file.path") == "projects/deep/alpha.md"
    assert get_field(n, "file.name") == "alpha"
    assert get_field(n, "file.folder") == "projects/deep"
    assert get_field(n, "file.ext") == "md"
    assert get_field(n, "file.size") == 42
    assert get_field(note(rel="top.md"), "file.folder") == ""


def test_truthiness_rules():
    assert not truthy(None)
    assert not truthy(False)
    assert not truthy("")
    assert not truthy([])
    assert not truthy({})
    assert truthy(0)  # 0 is a real value, unlike Python's bool(0)
    assert truthy("no")


def test_equality_inequality_and_numeric_interop():
    n = note({"status": "open", "n": 3})
    assert evaluate(where('status = "open"'), n)
    assert evaluate(where('status != "done"'), n)
    assert evaluate(where("n = 3"), n)
    assert evaluate(where("n >= 2.5"), n)  # int vs float compares fine


def test_bool_does_not_equal_int_one():
    n = note({"flag": True})
    assert not evaluate(where("flag = 1"), n)
    assert evaluate(where("flag = true"), n)


def test_date_comparisons():
    n = note({"due": datetime.date(2026, 7, 20)})
    assert evaluate(where("due <= 2026-07-31"), n)
    assert evaluate(where("due > 2026-07-01"), n)
    assert not evaluate(where("due > 2026-07-31"), n)


def test_incomparable_or_missing_operands_are_false_not_errors():
    n = note({"due": "someday", "n": 5})
    assert not evaluate(where("due < 2026-01-01"), n)  # str vs date
    assert not evaluate(where('n > "5"'), n)  # int vs str
    assert not evaluate(where("rating >= 3"), note({}))  # missing field
    assert evaluate(where("rating = null"), note({}))


def test_contains_and_in_operators():
    n = note({"tags": ["a", "b"], "title": "Deep Work", "meta": {"k": 1}})
    assert evaluate(where('tags CONTAINS "a"'), n)
    assert not evaluate(where('tags CONTAINS "z"'), n)
    assert evaluate(where('title CONTAINS "Deep"'), n)  # substring
    assert evaluate(where('meta CONTAINS "k"'), n)  # map key
    m = note({"status": "blocked"})
    assert evaluate(where('status IN ["open", "blocked"]'), m)
    assert not evaluate(where('status IN ["open", "done"]'), m)


def test_matches_regex_semantics():
    n = note({"title": "2026 planning"})
    assert evaluate(where('title MATCHES "^\\d{4}"'), n)
    assert not evaluate(where('title MATCHES "review$"'), n)
    assert not evaluate(where('n MATCHES "3"'), note({"n": 3}))  # non-string
    with pytest.raises(QueryError, match="invalid regex"):
        evaluate(where('title MATCHES "("'), n)


def test_bare_field_truthiness_and_boolean_combinations():
    assert matches(
        note({"due": datetime.date(2026, 1, 1)}), parse_query("WHERE due")
    )
    assert not matches(note({}), parse_query("WHERE due"))
    n = note({"status": "open", "priority": 1})
    assert evaluate(where('NOT status = "done" AND priority <= 2'), n)
    assert evaluate(where('status = "done" OR priority = 1'), n)


def test_from_sources_folders_tags_and_or_combination():
    by_folder = parse_query('FROM "proj"')
    assert matches(note(rel="proj/x.md"), by_folder)
    assert not matches(note(rel="projects/x.md"), by_folder)  # segment-safe
    by_tag = parse_query("FROM #Books")
    assert matches(note(tags=["books"]), by_tag)  # case-insensitive
    assert not matches(note(tags=["work"]), by_tag)
    combined = parse_query('FROM "projects", #books')
    assert matches(note(rel="projects/a.md"), combined)
    assert matches(note(rel="reading/b.md", tags=["books"]), combined)
    assert not matches(note(rel="journal/c.md"), combined)


def test_apply_query_filters_sorts_limits():
    notes = [
        note({"n": 3}, rel="c.md"),
        note({"n": 1}, rel="a.md"),
        note({"n": 2}, rel="b.md"),
        note({}, rel="d.md"),
    ]
    result = apply_query(notes, parse_query("WHERE n SORT n DESC LIMIT 2"))
    assert [item.rel for item in result] == ["c.md", "b.md"]
