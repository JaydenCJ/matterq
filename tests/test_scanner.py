"""Vault scanning: discovery rules, tag extraction, resilience."""

import pytest

from matterq.scanner import scan

from conftest import get_paths


def test_scan_discovers_markdown_recursively_in_sorted_order(sample_vault):
    notes, warnings = scan(sample_vault)
    assert get_paths(notes) == [
        "inbox.md",
        "projects/alpha.md",
        "projects/beta.md",
        "projects/gamma.md",
        "reading/book.md",
    ]
    assert warnings == []
    assert get_paths(scan(sample_vault)[0]) == get_paths(notes)  # stable


def test_non_markdown_and_dot_directories_are_skipped(make_vault):
    root = make_vault(
        {
            "a.md": "x",
            "b.txt": "y",
            "c.canvas": "z",
            ".obsidian/workspace.md": "w",
            ".git/HEAD.md": "h",
        }
    )
    notes, _ = scan(root)
    assert get_paths(notes) == ["a.md"]


def test_non_recursive_scan_stays_at_top_level(make_vault):
    root = make_vault({"top.md": "x", "sub/inner.md": "y"})
    notes, _ = scan(root, recursive=False)
    assert get_paths(notes) == ["top.md"]


def test_note_without_front_matter_has_only_tags_field(sample_vault):
    notes, _ = scan(sample_vault)
    inbox = notes[0]
    assert inbox.rel == "inbox.md"
    assert inbox.fields == {"tags": ["inbox"]}


def test_inline_tags_merge_after_front_matter_tags(sample_vault):
    notes, _ = scan(sample_vault)
    alpha = next(n for n in notes if n.rel == "projects/alpha.md")
    assert alpha.tags == ["work", "web", "q3"]
    assert alpha.fields["tags"] == ["work", "web", "q3"]


def test_tags_deduplicate_case_insensitively(make_vault):
    root = make_vault(
        {"n.md": "---\ntags: [Work]\n---\nBody #work #Work #other\n"}
    )
    notes, _ = scan(root)
    assert notes[0].tags == ["Work", "other"]


def test_tags_as_comma_separated_string_are_split(make_vault):
    root = make_vault({"n.md": "---\ntags: one, two\n---\n"})
    notes, _ = scan(root)
    assert notes[0].tags == ["one", "two"]


def test_headings_and_code_blocks_do_not_produce_tags(make_vault):
    root = make_vault(
        {
            "n.md": (
                "# Heading\n\nText with #real tag.\n\n"
                "```\n#!/bin/sh\necho #nope\n```\nAnd `#inline` too.\n"
            )
        }
    )
    notes, _ = scan(root)
    assert notes[0].tags == ["real"]


def test_broken_front_matter_yields_warning_not_crash(make_vault):
    root = make_vault(
        {
            "bad.md": '---\ntitle: "unclosed\n---\nBody #still-tagged\n',
            "ok.md": "x",
        }
    )
    notes, warnings = scan(root)
    assert get_paths(notes) == ["bad.md", "ok.md"]
    bad = notes[0]
    assert bad.error is not None
    assert bad.tags == ["still-tagged"]
    assert len(warnings) == 1 and warnings[0].startswith("bad.md:")


def test_file_size_recorded_and_missing_directory_raises(make_vault, tmp_path):
    root = make_vault({"n.md": "12345"})
    notes, _ = scan(root)
    assert notes[0].size == 5
    with pytest.raises(NotADirectoryError):
        scan(tmp_path / "nope")
