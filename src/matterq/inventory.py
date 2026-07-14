"""Field inventory: what keys exist across a vault, and of what type.

Powers ``matterq fields`` — the "what can I even query?" command you
run first against an unfamiliar vault.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, Iterator, List, Sequence, Tuple

from .scanner import Note

__all__ = ["field_stats"]


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, _dt.datetime):
        return "datetime"
    if isinstance(value, _dt.date):
        return "date"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "map"
    return "string"


def _flatten(fields: Dict[str, Any], prefix: str = "") -> Iterator[Tuple[str, Any]]:
    for key, value in fields.items():
        dotted = f"{prefix}{key}"
        yield dotted, value
        if isinstance(value, dict):
            yield from _flatten(value, prefix=f"{dotted}.")


def field_stats(notes: Sequence[Note]) -> List[Dict[str, Any]]:
    """Aggregate per-field usage over a vault.

    Returns one record per (dotted) field name with the number of notes
    using it, its coverage percentage, and the set of value types seen.
    Sorted by usage (descending), then name — so the interesting fields
    come first.
    """
    counts: Dict[str, int] = {}
    types: Dict[str, set] = {}
    for note in notes:
        for name, value in _flatten(note.fields):
            counts[name] = counts.get(name, 0) + 1
            types.setdefault(name, set()).add(_type_name(value))
    total = len(notes)
    records = []
    for name in sorted(counts, key=lambda k: (-counts[k], k)):
        coverage = 100 * counts[name] // total if total else 0
        records.append(
            {
                "field": name,
                "notes": counts[name],
                "coverage": f"{coverage}%",
                "types": ", ".join(sorted(types[name])),
            }
        )
    return records
