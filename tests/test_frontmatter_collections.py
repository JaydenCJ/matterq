"""Collections: flow lists/maps, block lists, nested block mappings."""

import datetime

import pytest

from matterq.frontmatter import FrontMatterError, parse_front_matter


def test_flow_lists_scalars_quoting_nesting():
    assert parse_front_matter("tags: [work, web, 3, true]") == {
        "tags": ["work", "web", 3, True]
    }
    assert parse_front_matter('tags: ["a, b", \'c\']') == {"tags": ["a, b", "c"]}
    assert parse_front_matter("grid: [[1, 2], [3, 4]]") == {
        "grid": [[1, 2], [3, 4]]
    }


def test_empty_flow_collections():
    assert parse_front_matter("a: []\nb: {}") == {"a": [], "b": {}}


def test_flow_maps_including_inside_lists():
    assert parse_front_matter("owner: {name: alice, level: 3}") == {
        "owner": {"name": "alice", "level": 3}
    }
    assert parse_front_matter("people: [{name: a}, {name: b}]") == {
        "people": [{"name": "a"}, {"name": "b"}]
    }


def test_block_list_indented_with_typed_items():
    fields = parse_front_matter(
        "xs:\n  - 2026-01-05\n  - 2.5\n  - null\n  - work"
    )
    assert fields == {"xs": [datetime.date(2026, 1, 5), 2.5, None, "work"]}


def test_block_list_at_same_indent_as_key():
    # YAML allows list items directly under the key without extra indent.
    fields = parse_front_matter("tags:\n- work\n- web\nstatus: open")
    assert fields == {"tags": ["work", "web"], "status": "open"}


def test_block_list_compact_pair_items():
    fields = parse_front_matter("steps:\n  - name: build\n  - name: test")
    assert fields == {"steps": [{"name": "build"}, {"name": "test"}]}


def test_nested_block_mappings_and_lists():
    fields = parse_front_matter(
        "project:\n"
        "  owner: alice\n"
        "  meta:\n"
        "    priority: 2\n"
        "  tags:\n"
        "    - a\n"
        "    - b\n"
        "status: open"
    )
    assert fields == {
        "project": {
            "owner": "alice",
            "meta": {"priority": 2},
            "tags": ["a", "b"],
        },
        "status": "open",
    }


def test_lenient_cases_null_value_and_duplicate_keys():
    # A key with no value is null; duplicates keep the last occurrence —
    # both show up constantly in real Obsidian-style vaults.
    assert parse_front_matter("draft:\nstatus: open") == {
        "draft": None,
        "status": "open",
    }
    assert parse_front_matter("status: draft\nstatus: final") == {
        "status": "final"
    }


def test_malformed_flow_collections_raise():
    with pytest.raises(FrontMatterError):
        parse_front_matter("tags: [a, b")
    with pytest.raises(FrontMatterError):
        parse_front_matter("tags: [a] extra")
