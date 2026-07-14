"""Scalar parsing: the leaf values of the front-matter subset.

These types drive query semantics (dates compare as dates, not
strings), so getting each coercion right — and each non-coercion,
like YAML 1.2 keeping "yes" a string — matters downstream.
"""

import datetime

import pytest

from matterq.frontmatter import FrontMatterError, parse_front_matter, parse_scalar


def test_string_styles_unquoted_double_single():
    assert parse_front_matter("title: Hello world") == {"title": "Hello world"}
    fields = parse_front_matter('title: "line1\\nline2 \\"quoted\\""')
    assert fields == {"title": 'line1\nline2 "quoted"'}
    assert parse_front_matter("title: 'it''s fine'") == {"title": "it's fine"}


def test_numbers_int_negative_float_exponent():
    fields = parse_front_matter("a: 42\nb: -7\nc: 3.14\nd: -0.5\ne: 1e3")
    assert fields == {"a": 42, "b": -7, "c": 3.14, "d": -0.5, "e": 1000.0}
    assert isinstance(fields["a"], int)


def test_booleans_case_insensitive():
    fields = parse_front_matter("a: true\nb: False\nc: TRUE")
    assert fields == {"a": True, "b": False, "c": True}


def test_yes_no_on_stay_strings():
    # YAML 1.2 core schema: the Norway problem must not happen.
    fields = parse_front_matter("country: no\nflag: yes\nswitch: on")
    assert fields == {"country": "no", "flag": "yes", "switch": "on"}


def test_null_variants():
    fields = parse_front_matter("a: null\nb: ~\nc:\nd: NULL")
    assert fields == {"a": None, "b": None, "c": None, "d": None}


def test_dates_and_datetimes_become_objects():
    fields = parse_front_matter(
        "due: 2026-08-01\na: 2026-08-01T09:30\nb: 2026-08-01 09:30:15"
    )
    assert fields["due"] == datetime.date(2026, 8, 1)
    assert fields["a"] == datetime.datetime(2026, 8, 1, 9, 30)
    assert fields["b"] == datetime.datetime(2026, 8, 1, 9, 30, 15)


def test_date_lookalikes_fall_back_to_string():
    # An impossible calendar date must not raise; versions stay strings.
    assert parse_scalar("2026-13-40") == "2026-13-40"
    assert parse_scalar("1.2.3") == "1.2.3"


def test_comments_and_hashes():
    fields = parse_front_matter(
        'status: open # not done yet\nurl: "a # b"\nchannel: news#general'
    )
    # A comment needs a preceding space; '#' inside quotes never counts.
    assert fields == {
        "status": "open",
        "url": "a # b",
        "channel": "news#general",
    }


def test_colon_inside_value_is_kept():
    fields = parse_front_matter(
        "title: Meeting: next steps\nurl: https://example.test/a"
    )
    assert fields == {
        "title": "Meeting: next steps",
        "url": "https://example.test/a",
    }


def test_malformed_quoting_raises():
    with pytest.raises(FrontMatterError):
        parse_front_matter('title: "never closed')
    with pytest.raises(FrontMatterError):
        parse_front_matter('title: "a" trailing')
