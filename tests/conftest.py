"""Shared fixtures: build small throwaway vaults under tmp_path."""

import textwrap

import pytest


@pytest.fixture
def make_vault(tmp_path):
    """Return a factory writing ``{relative_path: content}`` to a vault.

    Content is dedented so tests can use indented triple-quoted strings.
    """

    def _make(files):
        root = tmp_path / "vault"
        for rel, content in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(content), encoding="utf-8")
        root.mkdir(exist_ok=True)
        return root

    return _make


@pytest.fixture
def sample_vault(make_vault):
    """A small realistic vault used by engine/CLI tests."""
    return make_vault(
        {
            "projects/alpha.md": """\
                ---
                title: Alpha
                status: active
                due: 2026-08-01
                priority: 1
                tags: [work, web]
                ---
                Body of alpha. #q3
                """,
            "projects/beta.md": """\
                ---
                title: Beta
                status: active
                due: 2026-07-20
                priority: 2
                tags: [work]
                ---
                Body of beta.
                """,
            "projects/gamma.md": """\
                ---
                title: Gamma
                status: archived
                priority: 3
                tags: [work, writing]
                ---
                Body of gamma.
                """,
            "reading/book.md": """\
                ---
                title: A Book
                status: done
                rating: 5
                tags: [books]
                ---
                Great book. #reread
                """,
            "inbox.md": "No front matter here. #inbox\n",
        }
    )


def get_paths(notes):
    """Relative paths of notes, in order — the standard assertion shape."""
    return [note.rel for note in notes]
