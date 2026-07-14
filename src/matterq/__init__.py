"""matterq: query a folder of Markdown by front matter.

The public API mirrors the CLI: :func:`scan` a vault into notes,
:func:`parse_query` a query string, and :func:`apply_query` to filter,
sort, and limit. Everything is standard-library only.
"""

from .engine import apply_query, evaluate, get_field, matches
from .frontmatter import (
    FrontMatterError,
    load_document,
    parse_front_matter,
    split_front_matter,
)
from .query import Query, QueryError, parse_query
from .scanner import Note, scan

__version__ = "0.1.0"

__all__ = [
    "FrontMatterError",
    "Note",
    "Query",
    "QueryError",
    "apply_query",
    "evaluate",
    "get_field",
    "load_document",
    "matches",
    "parse_front_matter",
    "parse_query",
    "scan",
    "split_front_matter",
    "__version__",
]
