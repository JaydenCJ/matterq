"""Front-matter parsing: a small, dependency-free YAML subset.

matterq ships its own parser instead of depending on PyYAML. The subset
covers what real Markdown vaults put between ``---`` fences: scalars
(strings, ints, floats, booleans, null, dates, datetimes), flow
collections (``[a, b]``, ``{k: v}``), block lists, nested block
mappings, comments, and ``|``/``>`` block scalars. The exact rules are
documented in ``docs/frontmatter-subset.md``.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "FrontMatterError",
    "load_document",
    "parse_front_matter",
    "parse_scalar",
    "split_front_matter",
]


class FrontMatterError(ValueError):
    """Raised when a front-matter block cannot be parsed."""


_FM_OPEN = re.compile(r"^---\s*$")
_FM_CLOSE = re.compile(r"^(?:---|\.\.\.)\s*$")

_INT = re.compile(r"^[+-]?\d+$")
_FLOAT = re.compile(
    r"^[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?$|^[+-]?\d+[eE][+-]?\d+$"
)
_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_DATETIME = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?$"
)
_BLOCK_STYLES = ("|", "|-", "|+", ">", ">-", ">+")

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "0": "\0"}


def split_front_matter(text: str) -> Tuple[Optional[str], str]:
    """Split a Markdown document into ``(front_matter_text, body)``.

    The front matter is the block between an opening ``---`` on the very
    first line and the next ``---`` (or ``...``) line. Returns ``None``
    for the first element when the document has no front matter.
    """
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.split("\n")
    if not lines or not _FM_OPEN.match(lines[0]):
        return None, text
    for idx in range(1, len(lines)):
        if _FM_CLOSE.match(lines[idx]):
            return "\n".join(lines[1:idx]), "\n".join(lines[idx + 1 :])
    # An opening fence without a closing fence is a thematic break, not
    # front matter; treat the whole document as body.
    return None, text


def parse_front_matter(text: str) -> Dict[str, Any]:
    """Parse a raw front-matter block (without fences) into a dict."""
    parser = _BlockParser(text)
    return parser.parse()


def load_document(text: str) -> Tuple[Dict[str, Any], str]:
    """Parse a whole Markdown document; return ``(fields, body)``."""
    raw, body = split_front_matter(text)
    if raw is None:
        return {}, body
    return parse_front_matter(raw), body


def parse_scalar(token: str) -> Any:
    """Interpret an unquoted scalar token per the matterq subset.

    ``yes``/``no``/``on``/``off`` stay strings (YAML 1.2 semantics);
    only ``true``/``false`` (any case) are booleans.
    """
    t = token.strip()
    if t in ("", "~") or t.lower() == "null":
        return None
    low = t.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if _INT.match(t):
        return int(t)
    if _FLOAT.match(t):
        return float(t)
    m = _DATE.match(t)
    if m:
        try:
            return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return t  # looks like a date but is not one (e.g. 2026-13-40)
    m = _DATETIME.match(t)
    if m:
        try:
            return _dt.datetime(
                int(m.group(1)),
                int(m.group(2)),
                int(m.group(3)),
                int(m.group(4)),
                int(m.group(5)),
                int(m.group(6) or 0),
            )
        except ValueError:
            return t
    return t


def _strip_comment(line: str) -> str:
    """Remove a trailing ``# comment`` outside of quotes."""
    in_single = in_double = False
    i = 0
    while i < len(line):
        c = line[i]
        if in_single:
            if c == "'":
                if i + 1 < len(line) and line[i + 1] == "'":
                    i += 2
                    continue
                in_single = False
        elif in_double:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_double = False
        else:
            if c == "'":
                in_single = True
            elif c == '"':
                in_double = True
            elif c == "#" and (i == 0 or line[i - 1] in " \t"):
                return line[:i].rstrip()
        i += 1
    return line.rstrip()


def _parse_quoted(s: str, i: int) -> Tuple[str, int]:
    """Parse a quoted string starting at ``s[i]``; return (value, end)."""
    quote = s[i]
    out: List[str] = []
    i += 1
    while i < len(s):
        c = s[i]
        if quote == "'":
            if c == "'":
                if i + 1 < len(s) and s[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                return "".join(out), i + 1
            out.append(c)
            i += 1
        else:
            if c == "\\" and i + 1 < len(s):
                out.append(_ESCAPES.get(s[i + 1], s[i + 1]))
                i += 2
                continue
            if c == '"':
                return "".join(out), i + 1
            out.append(c)
            i += 1
    raise FrontMatterError(f"unterminated {quote} string: {s!r}")


class _FlowParser:
    """Recursive-descent parser for flow collections: [..] and {..}."""

    def __init__(self, text: str) -> None:
        self.s = text
        self.i = 0

    def parse(self) -> Any:
        value = self._value()
        self._skip_ws()
        if self.i != len(self.s):
            raise FrontMatterError(
                f"trailing characters after flow value: {self.s[self.i:]!r}"
            )
        return value

    def _skip_ws(self) -> None:
        while self.i < len(self.s) and self.s[self.i] in " \t":
            self.i += 1

    def _value(self) -> Any:
        self._skip_ws()
        if self.i >= len(self.s):
            raise FrontMatterError("unexpected end of flow value")
        c = self.s[self.i]
        if c == "[":
            return self._list()
        if c == "{":
            return self._map()
        if c in "\"'":
            value, self.i = _parse_quoted(self.s, self.i)
            return value
        return parse_scalar(self._plain())

    def _plain(self) -> str:
        start = self.i
        while self.i < len(self.s) and self.s[self.i] not in ",]}:":
            self.i += 1
        if start == self.i:
            raise FrontMatterError(
                f"unexpected character in flow value: {self.s[self.i]!r}"
            )
        return self.s[start : self.i].strip()

    def _list(self) -> List[Any]:
        self.i += 1  # consume '['
        items: List[Any] = []
        self._skip_ws()
        if self.i < len(self.s) and self.s[self.i] == "]":
            self.i += 1
            return items
        while True:
            items.append(self._value())
            self._skip_ws()
            if self.i >= len(self.s):
                raise FrontMatterError("unterminated flow list")
            c = self.s[self.i]
            self.i += 1
            if c == "]":
                return items
            if c != ",":
                raise FrontMatterError(f"expected ',' or ']', got {c!r}")

    def _map(self) -> Dict[str, Any]:
        self.i += 1  # consume '{'
        out: Dict[str, Any] = {}
        self._skip_ws()
        if self.i < len(self.s) and self.s[self.i] == "}":
            self.i += 1
            return out
        while True:
            self._skip_ws()
            if self.i < len(self.s) and self.s[self.i] in "\"'":
                key, self.i = _parse_quoted(self.s, self.i)
            else:
                key = self._plain()
            self._skip_ws()
            if self.i >= len(self.s) or self.s[self.i] != ":":
                raise FrontMatterError("expected ':' in flow mapping")
            self.i += 1
            out[str(key)] = self._value()
            self._skip_ws()
            if self.i >= len(self.s):
                raise FrontMatterError("unterminated flow mapping")
            c = self.s[self.i]
            self.i += 1
            if c == "}":
                return out
            if c != ",":
                raise FrontMatterError(f"expected ',' or '}}', got {c!r}")


def _parse_value(rest: str) -> Any:
    """Parse the value part of a ``key: value`` line (comment-stripped)."""
    rest = rest.strip()
    if not rest:
        return None
    if rest[0] in "[{":
        return _FlowParser(rest).parse()
    if rest[0] in "\"'":
        value, end = _parse_quoted(rest, 0)
        if rest[end:].strip():
            raise FrontMatterError(
                f"unexpected text after quoted string: {rest[end:].strip()!r}"
            )
        return value
    return parse_scalar(rest)


class _BlockParser:
    """Indentation-based parser for the block layer of the subset."""

    def __init__(self, text: str) -> None:
        self.raw = text.split("\n")
        self.lines: List[Tuple[int, str, int]] = []
        for raw_idx, raw in enumerate(self.raw):
            leading = raw[: len(raw) - len(raw.lstrip())]
            if "\t" in leading:
                raise FrontMatterError(
                    f"tabs are not allowed in indentation (line {raw_idx + 1})"
                )
            stripped = _strip_comment(raw)
            content = stripped.strip()
            if not content:
                continue
            indent = len(stripped) - len(stripped.lstrip(" "))
            self.lines.append((indent, content, raw_idx))
        self.i = 0

    def parse(self) -> Dict[str, Any]:
        if not self.lines:
            return {}
        if self.lines[0][0] != 0:
            raise FrontMatterError("top-level keys must not be indented")
        result = self._parse_map(0)
        if self.i < len(self.lines):
            _, content, raw_idx = self.lines[self.i]
            raise FrontMatterError(
                f"unexpected content at line {raw_idx + 1}: {content!r}"
            )
        return result

    @staticmethod
    def _is_list_item(content: str) -> bool:
        return content == "-" or content.startswith("- ")

    def _parse_map(self, indent: int) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        while self.i < len(self.lines):
            ind, content, raw_idx = self.lines[self.i]
            if ind < indent:
                break
            if ind > indent:
                raise FrontMatterError(
                    f"unexpected indentation at line {raw_idx + 1}: {content!r}"
                )
            if self._is_list_item(content):
                break
            key, rest = self._split_key(content, raw_idx)
            self.i += 1
            if rest in _BLOCK_STYLES:
                out[key] = self._block_scalar(rest, indent, raw_idx)
            elif rest:
                out[key] = _parse_value(rest)
            else:
                out[key] = self._nested_value(indent)
        return out

    def _nested_value(self, indent: int) -> Any:
        """Value for a ``key:`` line with nothing after the colon."""
        if self.i >= len(self.lines):
            return None
        nxt_ind, nxt_content, _ = self.lines[self.i]
        if self._is_list_item(nxt_content) and nxt_ind >= indent:
            return self._parse_list(nxt_ind)
        if nxt_ind > indent:
            return self._parse_map(nxt_ind)
        return None

    def _parse_list(self, indent: int) -> List[Any]:
        out: List[Any] = []
        while self.i < len(self.lines):
            ind, content, raw_idx = self.lines[self.i]
            if ind != indent or not self._is_list_item(content):
                break
            rest = content[1:].strip()
            self.i += 1
            if not rest:
                out.append(None)
            elif ":" in rest and self._looks_like_pair(rest):
                # Compact single-pair mapping item: "- key: value".
                key, value = self._split_key(rest, raw_idx)
                out.append({key: _parse_value(value) if value else None})
            else:
                out.append(_parse_value(rest))
        return out

    @staticmethod
    def _looks_like_pair(rest: str) -> bool:
        if rest[0] in "\"'[{":
            return False
        for idx, ch in enumerate(rest):
            if ch == ":" and (idx + 1 == len(rest) or rest[idx + 1] in " \t"):
                return True
        return False

    @staticmethod
    def _split_key(content: str, raw_idx: int) -> Tuple[str, str]:
        if content[0] in "\"'":
            key, end = _parse_quoted(content, 0)
            rest = content[end:].lstrip()
            if not rest.startswith(":"):
                raise FrontMatterError(
                    f"expected ':' after quoted key (line {raw_idx + 1})"
                )
            return key, rest[1:].strip()
        for idx, ch in enumerate(content):
            if ch == ":" and (
                idx + 1 == len(content) or content[idx + 1] in " \t"
            ):
                key = content[:idx].strip()
                if not key:
                    raise FrontMatterError(
                        f"empty mapping key at line {raw_idx + 1}"
                    )
                return key, content[idx + 1 :].strip()
        raise FrontMatterError(
            f"expected 'key: value' at line {raw_idx + 1}: {content!r}"
        )

    def _block_scalar(self, style: str, key_indent: int, raw_idx: int) -> str:
        """Consume a ``|`` or ``>`` block scalar from the raw lines."""
        block: List[str] = []
        first_indent: Optional[int] = None
        j = raw_idx + 1
        while j < len(self.raw):
            raw = self.raw[j]
            if not raw.strip():
                block.append("")
                j += 1
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            if indent <= key_indent:
                break
            if first_indent is None:
                first_indent = indent
            block.append(raw[min(first_indent, indent) :])
            j += 1
        while block and block[-1] == "":
            block.pop()
        # Skip structural lines that belong to the scalar's raw range.
        while self.i < len(self.lines) and self.lines[self.i][2] < j:
            self.i += 1
        if style.startswith("|"):
            return "\n".join(block)
        paragraphs: List[str] = []
        current: List[str] = []
        for line in block:
            if line == "":
                paragraphs.append(" ".join(current))
                current = []
            else:
                current.append(line)
        paragraphs.append(" ".join(current))
        return "\n".join(paragraphs)
