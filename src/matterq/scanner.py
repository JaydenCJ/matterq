"""Vault scanning: discover Markdown notes and their queryable fields.

A "vault" is just a folder. :func:`scan` walks it, parses every
``.md``/``.markdown`` file's front matter, extracts inline ``#tags``
from the body (skipping code blocks), and returns deterministic,
path-sorted :class:`Note` objects. A note that fails to parse is never
fatal: it is returned with empty fields and a warning message.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

from .frontmatter import FrontMatterError, load_document

__all__ = ["Note", "scan", "read_note"]

_MARKDOWN_SUFFIXES = (".md", ".markdown")

# An inline tag: '#' not preceded by a word character or another '#',
# followed by a letter, then word chars, '/', or '-'. Headings ("# Title")
# never match because a space cannot start a tag.
_TAG = re.compile(r"(?<![\w#])#([A-Za-z][\w/-]*)")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_FENCE = re.compile(r"^(?:```|~~~)")


@dataclass
class Note:
    """One Markdown file: its parsed front matter plus file metadata."""

    path: Path
    rel: str  # POSIX-style path relative to the vault root
    fields: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    size: int = 0
    error: Optional[str] = None


def _body_tags(body: str) -> List[str]:
    """Extract inline #tags, ignoring fenced code blocks and code spans."""
    kept: List[str] = []
    in_fence = False
    for line in body.split("\n"):
        if _FENCE.match(line.lstrip()):
            in_fence = not in_fence
            continue
        if not in_fence:
            kept.append(_INLINE_CODE.sub("", line))
    return _TAG.findall("\n".join(kept))


def _front_matter_tags(value: Any) -> List[str]:
    """Normalize a front-matter ``tags`` value into a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[,\s]+", value)
    elif isinstance(value, list):
        parts = [str(item) for item in value if item is not None]
    else:
        parts = [str(value)]
    return [p.lstrip("#") for p in parts if p.lstrip("#")]


def _merge_tags(fm_tags: List[str], inline: List[str]) -> List[str]:
    merged: List[str] = []
    seen = set()
    for tag in fm_tags + inline:
        key = tag.casefold()
        if key not in seen:
            seen.add(key)
            merged.append(tag)
    return merged


def read_note(path: Path, rel: str) -> Note:
    """Parse one Markdown file into a Note (never raises for bad YAML)."""
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    note = Note(path=path, rel=rel, size=len(data))
    try:
        fields, body = load_document(text)
    except FrontMatterError as exc:
        note.error = str(exc)
        note.tags = _merge_tags([], _body_tags(text))
        note.fields["tags"] = list(note.tags)
        return note
    note.fields = fields
    note.tags = _merge_tags(
        _front_matter_tags(fields.get("tags")), _body_tags(body)
    )
    note.fields["tags"] = list(note.tags)
    return note


def scan(
    root: Path, recursive: bool = True
) -> Tuple[List[Note], List[str]]:
    """Walk ``root`` and return ``(notes, warnings)``.

    Notes are sorted by relative path so every run is deterministic.
    Dot-directories (``.obsidian``, ``.git``, ...) are skipped.
    """
    root = Path(root)
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")
    notes: List[Note] = []
    warnings: List[str] = []
    pattern = "**/*" if recursive else "*"
    candidates = []
    for path in root.glob(pattern):
        if not path.is_file() or path.suffix.lower() not in _MARKDOWN_SUFFIXES:
            continue
        rel_parts = path.relative_to(root).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        candidates.append((str(PurePosixPath(*rel_parts)), path))
    for rel, path in sorted(candidates):
        note = read_note(path, rel)
        if note.error:
            warnings.append(f"{rel}: {note.error}")
        notes.append(note)
    return notes, warnings
