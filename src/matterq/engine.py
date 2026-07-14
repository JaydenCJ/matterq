"""Query evaluation: field resolution, expression semantics, sort, limit.

Semantics are deliberately forgiving, in the spirit of querying messy
personal notes: a missing field is ``null``, an ordered comparison
between incompatible types is simply ``false`` (never an exception),
and ``null`` always sorts last regardless of direction.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import PurePosixPath
from typing import Any, List

from .query import And, Cmp, Expr, Field, Lit, Not, Or, Query, QueryError
from .scanner import Note

__all__ = ["apply_query", "evaluate", "get_field", "matches", "truthy"]


# --- Field resolution -------------------------------------------------


def get_field(note: Note, name: str) -> Any:
    """Resolve a (possibly dotted) field name against a note.

    ``file.path``, ``file.name``, ``file.folder``, ``file.ext``, and
    ``file.size`` are implicit metadata fields; everything else is
    looked up in the front matter, descending into nested mappings.
    """
    if name.startswith("file."):
        posix = PurePosixPath(note.rel)
        sub = name[5:]
        if sub == "path":
            return note.rel
        if sub == "name":
            return posix.stem
        if sub == "ext":
            return posix.suffix.lstrip(".")
        if sub == "folder":
            parent = str(posix.parent)
            return "" if parent == "." else parent
        if sub == "size":
            return note.size
        return None
    current: Any = note.fields
    for part in name.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


# --- Expression evaluation --------------------------------------------


def truthy(value: Any) -> bool:
    """Query-language truthiness: null, false, "", [] and {} are false."""
    if value is None or value is False:
        return False
    if isinstance(value, (str, list, dict)) and len(value) == 0:
        return False
    return True


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _orderable(left: Any, right: Any) -> bool:
    """True when ``<``/``>`` comparisons between the values make sense."""
    if _is_number(left) and _is_number(right):
        return True
    if isinstance(left, str) and isinstance(right, str):
        return True
    if isinstance(left, _dt.datetime) and isinstance(right, _dt.datetime):
        return True
    if (
        isinstance(left, _dt.date)
        and isinstance(right, _dt.date)
        and not isinstance(left, _dt.datetime)
        and not isinstance(right, _dt.datetime)
    ):
        return True
    return False


def _equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) != isinstance(right, bool):
        return False  # avoid Python's true == 1 surprise
    if isinstance(left, _dt.datetime) != isinstance(right, _dt.datetime):
        return False
    return left == right


def _contains(container: Any, item: Any) -> bool:
    if isinstance(container, list):
        return any(_equal(element, item) for element in container)
    if isinstance(container, str):
        return isinstance(item, str) and item in container
    if isinstance(container, dict):
        return isinstance(item, str) and item in container
    return False


def _compare(op: str, left: Any, right: Any) -> bool:
    if op == "=":
        return _equal(left, right)
    if op == "!=":
        return not _equal(left, right)
    if op == "contains":
        return _contains(left, right)
    if op == "in":
        return _contains(right, left)
    if op == "matches":
        if not isinstance(left, str) or not isinstance(right, str):
            return False
        try:
            return re.search(right, left) is not None
        except re.error as exc:
            raise QueryError(f"invalid regex {right!r}: {exc}") from exc
    if not _orderable(left, right):
        return False
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    raise QueryError(f"unknown operator {op!r}")


def evaluate(expr: Expr, note: Note) -> Any:
    """Evaluate an expression AST against one note."""
    if isinstance(expr, Lit):
        return expr.value
    if isinstance(expr, Field):
        return get_field(note, expr.name)
    if isinstance(expr, Not):
        return not truthy(evaluate(expr.operand, note))
    if isinstance(expr, And):
        return truthy(evaluate(expr.left, note)) and truthy(
            evaluate(expr.right, note)
        )
    if isinstance(expr, Or):
        return truthy(evaluate(expr.left, note)) or truthy(
            evaluate(expr.right, note)
        )
    if isinstance(expr, Cmp):
        return _compare(
            expr.op, evaluate(expr.left, note), evaluate(expr.right, note)
        )
    raise QueryError(f"unknown expression node {expr!r}")


# --- Sources, sorting, limiting ---------------------------------------


def _in_folder(note: Note, folder: str) -> bool:
    if folder in ("", "."):
        return True
    return note.rel == folder or note.rel.startswith(folder + "/")


def _has_tag(note: Note, tag: str) -> bool:
    wanted = tag.casefold()
    return any(t.casefold() == wanted for t in note.tags)


def matches(note: Note, query: Query) -> bool:
    """True when the note passes the query's FROM and WHERE clauses."""
    if query.folders or query.from_tags:
        from_ok = any(_in_folder(note, f) for f in query.folders) or any(
            _has_tag(note, t) for t in query.from_tags
        )
        if not from_ok:
            return False
    if query.where is not None:
        return truthy(evaluate(query.where, note))
    return True


class _Reversed:
    """Wrapper inverting comparisons, for per-key DESC in one sort pass."""

    __slots__ = ("key",)

    def __init__(self, key: Any) -> None:
        self.key = key

    def __lt__(self, other: "_Reversed") -> bool:
        return other.key < self.key

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Reversed) and self.key == other.key


def _sort_rank(value: Any) -> Any:
    """A totally ordered surrogate: (missing, type-rank, comparable)."""
    if value is None:
        return (1, 0, 0)
    if isinstance(value, bool):
        return (0, 0, int(value))
    if _is_number(value):
        return (0, 1, float(value))
    if isinstance(value, (_dt.date, _dt.datetime)):
        return (0, 2, value.isoformat())
    if isinstance(value, str):
        return (0, 3, (value.casefold(), value))
    if isinstance(value, list):
        return (0, 4, json.dumps(value, sort_keys=True, default=str))
    return (0, 5, json.dumps(value, sort_keys=True, default=str))


def _sort_key(note: Note, query: Query) -> Any:
    parts = []
    for name, desc in query.sort:
        missing, type_rank, comparable = _sort_rank(get_field(note, name))
        inner = (type_rank, comparable)
        # null sorts last in both directions, so only the value part flips.
        parts.append((missing, _Reversed(inner) if desc else inner))
    parts.append(note.rel)  # stable, deterministic tiebreaker
    return tuple(parts)


def apply_query(notes: List[Note], query: Query) -> List[Note]:
    """Filter, sort, and limit notes according to a parsed query."""
    selected = [note for note in notes if matches(note, query)]
    if query.sort:
        selected.sort(key=lambda note: _sort_key(note, query))
    if query.limit is not None:
        selected = selected[: query.limit]
    return selected
