"""Whole documents: fence splitting, block scalars, structural errors."""

import pytest

from matterq.frontmatter import (
    FrontMatterError,
    load_document,
    parse_front_matter,
    split_front_matter,
)


def test_split_and_load_basic_document():
    raw, body = split_front_matter("---\ntitle: Hi\n---\nBody text\n")
    assert raw == "title: Hi"
    assert body == "Body text\n"
    fields, body = load_document("---\nn: 3\n---\nhello")
    assert fields == {"n": 3}
    assert body == "hello"


def test_front_matter_must_start_on_first_line():
    assert split_front_matter("Just a note.\n")[0] is None
    assert split_front_matter("\n---\ntitle: Hi\n---\n")[0] is None


def test_unclosed_fence_is_body_not_front_matter():
    # "---" then no closing fence is a thematic break, not metadata.
    raw, body = split_front_matter("---\njust a horizontal rule story\n")
    assert raw is None
    assert "horizontal rule" in body


def test_dots_fence_bom_and_empty_block():
    assert split_front_matter("---\na: 1\n...\nbody")[0] == "a: 1"
    assert split_front_matter("﻿---\na: 1\n---\n")[0] == "a: 1"
    assert load_document("---\n---\nbody")[0] == {}


def test_literal_block_scalar_preserves_lines_and_indent():
    fields = parse_front_matter(
        "description: |\n  first line\n  second line\nstatus: open"
    )
    assert fields["description"] == "first line\nsecond line"
    assert fields["status"] == "open"
    fields = parse_front_matter("code: |\n  def f():\n      return 1")
    assert fields["code"] == "def f():\n    return 1"


def test_folded_block_scalar_joins_lines():
    fields = parse_front_matter("summary: >\n  one\n  two\n\n  new paragraph")
    assert fields["summary"] == "one two\nnew paragraph"


def test_block_scalar_content_is_taken_verbatim():
    fields = parse_front_matter("notes: |\n  a\n\n  b\ndone: true")
    assert fields["notes"] == "a\n\nb"
    assert fields["done"] is True
    fields = parse_front_matter("raw: |\n  - not: a list\n  key: value")
    assert fields["raw"] == "- not: a list\nkey: value"


def test_full_line_comments_are_skipped():
    fields = parse_front_matter("# header comment\na: 1\n# middle\nb: 2")
    assert fields == {"a": 1, "b": 2}


def test_structural_errors_have_helpful_messages():
    with pytest.raises(FrontMatterError, match="line 2"):
        parse_front_matter("a:\n\tb: 1")  # tab indentation
    with pytest.raises(FrontMatterError, match="top-level"):
        parse_front_matter("  a: 1")
    with pytest.raises(FrontMatterError, match="key: value"):
        parse_front_matter("just some words")


def test_quoted_keys_and_crlf_line_endings():
    assert parse_front_matter('"weird key": 1') == {"weird key": 1}
    fields, body = load_document("---\r\na: 1\r\n---\r\nbody\r\n")
    assert fields == {"a": 1}
    assert "body" in body
