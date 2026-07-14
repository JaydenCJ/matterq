"""Query parsing: clause handling, expression precedence, error cases."""

import datetime

import pytest

from matterq.query import (
    And,
    Cmp,
    Field,
    Lit,
    Not,
    Or,
    QueryError,
    parse_query,
)


def test_empty_query_matches_everything():
    query = parse_query("")
    assert query.select is None
    assert query.where is None
    assert query.sort == []
    assert query.limit is None


def test_select_variants():
    assert parse_query("SELECT title, due, file.name").select == [
        "title",
        "due",
        "file.name",
    ]
    assert parse_query("SELECT *").select is None  # * == no projection
    assert parse_query('SELECT "read on"').select == ["read on"]


def test_from_sources_folders_and_tags():
    query = parse_query('FROM "projects/", #books')
    assert query.folders == ["projects"]  # slashes normalized away
    assert query.from_tags == ["books"]


def test_keywords_are_case_insensitive():
    query = parse_query(
        'select title where status = "open" sort due desc limit 3'
    )
    assert query.select == ["title"]
    assert query.limit == 3
    assert query.sort == [("due", True)]


def test_comparison_ast_and_double_equals_alias():
    assert parse_query('WHERE status = "open"').where == Cmp(
        "=", Field("status"), Lit("open")
    )
    assert parse_query("WHERE a == 1").where == Cmp("=", Field("a"), Lit(1))


def test_boolean_precedence_parens_and_not():
    assert parse_query("WHERE a OR b AND c").where == Or(
        Field("a"), And(Field("b"), Field("c"))
    )
    assert parse_query("WHERE (a OR b) AND c").where == And(
        Or(Field("a"), Field("b")), Field("c")
    )
    assert parse_query("WHERE NOT a AND b").where == And(
        Not(Field("a")), Field("b")
    )


def test_literal_types_dates_numbers_bools_null():
    assert parse_query("WHERE due <= 2026-07-31").where.right == Lit(
        datetime.date(2026, 7, 31)
    )
    assert parse_query("WHERE at < 2026-07-31T09:30").where.right == Lit(
        datetime.datetime(2026, 7, 31, 9, 30)
    )
    assert parse_query("WHERE delta > -5").where.right == Lit(-5)
    query = parse_query("WHERE a = true AND b = false AND c = null")
    assert query.where.left.left.right == Lit(True)
    assert query.where.right.right == Lit(None)


def test_contains_in_matches_and_list_literals():
    assert parse_query('WHERE tags CONTAINS "x"').where.op == "contains"
    assert parse_query('WHERE title MATCHES "^A"').where.op == "matches"
    query = parse_query('WHERE status IN ["open", "blocked"]')
    assert query.where.op == "in"
    assert query.where.right == Lit(["open", "blocked"])
    assert parse_query("WHERE d IN [2026-01-01]").where.right == Lit(
        [datetime.date(2026, 1, 1)]
    )


def test_bare_tag_in_where_is_tag_membership():
    query = parse_query("WHERE #urgent")
    assert query.where == Cmp("contains", Field("tags"), Lit("urgent"))


def test_sort_multiple_keys_with_directions():
    query = parse_query("SORT priority ASC, due DESC, title")
    assert query.sort == [
        ("priority", False),
        ("due", True),
        ("title", False),
    ]


def test_regex_escapes_survive_double_quoted_strings():
    # "\d" must reach MATCHES intact, not be collapsed to "d".
    assert parse_query('WHERE t MATCHES "^\\d{4}"').where.right == Lit(
        "^\\d{4}"
    )


def test_impossible_date_literals_raise_query_error_not_value_error():
    # 2026-13-40 tokenizes as a date but is not one; the CLI catches
    # QueryError (exit 2), so ValueError here would mean a traceback.
    with pytest.raises(QueryError, match="invalid date literal"):
        parse_query("WHERE due = 2026-13-40")
    with pytest.raises(QueryError, match="invalid date literal"):
        parse_query("WHERE at < 2026-07-31T25:61")


def test_malformed_queries_raise_query_error():
    with pytest.raises(QueryError, match="positive integer"):
        parse_query("LIMIT 0")
    with pytest.raises(QueryError, match="positive integer"):
        parse_query("LIMIT 2.5")
    with pytest.raises(QueryError, match="unexpected"):
        parse_query("WHERE a = 1 SELECT title")  # clauses out of order
    with pytest.raises(QueryError, match="unexpected"):
        parse_query("SELECT title xyzzy")  # trailing garbage
    with pytest.raises(QueryError, match="unterminated"):
        parse_query('WHERE a = "oops')
    with pytest.raises(QueryError, match="FROM expects"):
        parse_query("FROM status")
    with pytest.raises(QueryError, match="unexpected character"):
        parse_query("WHERE a = 1 ; drop")
