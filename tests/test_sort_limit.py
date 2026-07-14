"""Sorting semantics: direction, multi-key, null placement, mixed types."""

import datetime

from matterq.engine import apply_query
from matterq.query import parse_query
from matterq.scanner import Note


def note(rel, **fields):
    return Note(path=None, rel=rel, fields=fields)


def run(notes, query_text):
    return [n.rel for n in apply_query(notes, parse_query(query_text))]


def test_sort_directions_default_asc():
    notes = [note("b.md", n=2), note("a.md", n=1), note("c.md", n=3)]
    assert run(notes, "SORT n") == ["a.md", "b.md", "c.md"]
    assert run(notes, "SORT n DESC") == ["c.md", "b.md", "a.md"]


def test_null_sorts_last_in_both_directions():
    notes = [note("none.md"), note("low.md", n=1), note("high.md", n=9)]
    assert run(notes, "SORT n ASC") == ["low.md", "high.md", "none.md"]
    assert run(notes, "SORT n DESC") == ["high.md", "low.md", "none.md"]


def test_multi_key_sort_with_mixed_directions_and_path_ties():
    notes = [
        note("a.md", group="x", n=1),
        note("b.md", group="x", n=2),
        note("c.md", group="y", n=3),
    ]
    assert run(notes, "SORT group ASC, n DESC") == ["b.md", "a.md", "c.md"]
    ties = [note("z.md", n=1), note("a.md", n=1), note("m.md", n=1)]
    assert run(ties, "SORT n") == ["a.md", "m.md", "z.md"]  # deterministic


def test_string_sort_is_case_insensitive_but_deterministic():
    notes = [
        note("1.md", t="banana"),
        note("2.md", t="Apple"),
        note("3.md", t="apple"),
    ]
    order = run(notes, "SORT t")
    assert order[2] == "1.md"  # banana last
    assert set(order[:2]) == {"2.md", "3.md"}
    assert order == run(list(reversed(notes)), "SORT t")  # order-independent


def test_dates_and_mixed_types_sort_without_errors():
    notes = [
        note("later.md", due=datetime.date(2026, 9, 1)),
        note("sooner.md", due=datetime.date(2026, 7, 1)),
    ]
    assert run(notes, "SORT due") == ["sooner.md", "later.md"]
    mixed = [note("s.md", v="text"), note("n.md", v=7), note("b.md", v=True)]
    # bools < numbers < strings; the point is: no TypeError, stable order.
    assert run(mixed, "SORT v") == ["b.md", "n.md", "s.md"]


def test_limit_applies_after_sort_and_respects_scan_order_otherwise():
    notes = [note("a.md", n=1), note("b.md", n=2), note("c.md", n=3)]
    assert run(notes, "SORT n DESC LIMIT 1") == ["c.md"]
    assert run(notes, "LIMIT 2") == ["a.md", "b.md"]
