"""The matterq query language: tokenizer, parser, and AST.

Grammar (all clauses optional, in this order)::

    SELECT field, ...  | SELECT *
    FROM "folder" | #tag  (, more sources; comma = OR)
    WHERE <expr>
    SORT field [ASC|DESC], ...
    LIMIT n

Expression grammar (lowest to highest precedence)::

    expr    := and (OR and)*
    and     := unary (AND unary)*
    unary   := NOT unary | comparison
    compare := primary (op primary)?     op: = == != < <= > >=
                                             CONTAINS | IN | MATCHES
    primary := literal | field | ( expr )

Keywords are case-insensitive. Literals: "str", 'str', numbers,
dates (2026-01-31), datetimes, true/false/null.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field as _field
from typing import Any, List, Optional, Tuple, Union

__all__ = [
    "And",
    "Cmp",
    "Field",
    "Lit",
    "Not",
    "Or",
    "Query",
    "QueryError",
    "parse_query",
]


class QueryError(ValueError):
    """Raised for a malformed query or an invalid regex at eval time."""


# --- AST -------------------------------------------------------------


@dataclass(frozen=True)
class Lit:
    value: Any


@dataclass(frozen=True)
class Field:
    name: str


@dataclass(frozen=True)
class Not:
    operand: "Expr"


@dataclass(frozen=True)
class And:
    left: "Expr"
    right: "Expr"


@dataclass(frozen=True)
class Or:
    left: "Expr"
    right: "Expr"


@dataclass(frozen=True)
class Cmp:
    op: str  # "=", "!=", "<", "<=", ">", ">=", "contains", "in", "matches"
    left: "Expr"
    right: "Expr"


Expr = Union[Lit, Field, Not, And, Or, Cmp]


@dataclass
class Query:
    """A parsed query, ready for :func:`matterq.engine.apply_query`."""

    select: Optional[List[str]] = None  # None = no projection requested
    folders: List[str] = _field(default_factory=list)
    from_tags: List[str] = _field(default_factory=list)
    where: Optional[Expr] = None
    sort: List[Tuple[str, bool]] = _field(default_factory=list)  # (field, desc)
    limit: Optional[int] = None


# --- Tokenizer -------------------------------------------------------

_KEYWORDS = {
    "SELECT",
    "FROM",
    "WHERE",
    "SORT",
    "LIMIT",
    "ASC",
    "DESC",
    "AND",
    "OR",
    "NOT",
    "CONTAINS",
    "IN",
    "MATCHES",
    "TRUE",
    "FALSE",
    "NULL",
}

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_IDENT = re.compile(r"[A-Za-z_][\w.-]*")
_TAGTOK = re.compile(r"#[A-Za-z][\w/-]*")


@dataclass(frozen=True)
class _Token:
    kind: str  # KW, IDENT, STR, NUM, DATE, TAG, OP, LPAREN, RPAREN, COMMA, STAR
    value: Any
    pos: int


def _tokenize(text: str) -> List[_Token]:
    tokens: List[_Token] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c in "\"'":
            value, end = _read_string(text, i)
            tokens.append(_Token("STR", value, i))
            i = end
            continue
        if c == "#":
            m = _TAGTOK.match(text, i)
            if not m:
                raise QueryError(f"invalid tag at position {i}")
            tokens.append(_Token("TAG", m.group(0)[1:], i))
            i = m.end()
            continue
        if c.isdigit() or (c in "+-" and i + 1 < n and text[i + 1].isdigit()):
            sign = ""
            j = i
            if c in "+-":
                sign = c
                j += 1
            m = _DATETIME.match(text, j) or _DATE.match(text, j)
            if m and not sign:
                tokens.append(_Token("DATE", m.group(0), i))
                i = m.end()
                continue
            m = _NUMBER.match(text, j)
            if not m:
                raise QueryError(f"invalid number at position {i}")
            raw = sign + m.group(0)
            number = float(raw) if "." in raw else int(raw)
            tokens.append(_Token("NUM", number, i))
            i = m.end()
            continue
        if c == "!" and text[i : i + 2] == "!=":
            tokens.append(_Token("OP", "!=", i))
            i += 2
            continue
        if c in "<>":
            op = text[i : i + 2] if text[i : i + 2] in ("<=", ">=") else c
            tokens.append(_Token("OP", op, i))
            i += len(op)
            continue
        if c == "=":
            op = "==" if text[i : i + 2] == "==" else "="
            tokens.append(_Token("OP", "=", i))
            i += len(op)
            continue
        if c == "(":
            tokens.append(_Token("LPAREN", c, i))
            i += 1
            continue
        if c == ")":
            tokens.append(_Token("RPAREN", c, i))
            i += 1
            continue
        if c == "[":
            tokens.append(_Token("LBRACKET", c, i))
            i += 1
            continue
        if c == "]":
            tokens.append(_Token("RBRACKET", c, i))
            i += 1
            continue
        if c == ",":
            tokens.append(_Token("COMMA", c, i))
            i += 1
            continue
        if c == "*":
            tokens.append(_Token("STAR", c, i))
            i += 1
            continue
        m = _IDENT.match(text, i)
        if m:
            word = m.group(0)
            upper = word.upper()
            if upper in _KEYWORDS:
                tokens.append(_Token("KW", upper, i))
            else:
                tokens.append(_Token("IDENT", word, i))
            i = m.end()
            continue
        raise QueryError(f"unexpected character {c!r} at position {i}")
    return tokens


def _read_string(text: str, i: int) -> Tuple[str, int]:
    quote = text[i]
    start = i
    out: List[str] = []
    i += 1
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text) and quote == '"':
            nxt = text[i + 1]
            # Unknown escapes keep the backslash so "\d" works in MATCHES.
            escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
            out.append(escapes.get(nxt, "\\" + nxt))
            i += 2
            continue
        if c == quote:
            return "".join(out), i + 1
        out.append(c)
        i += 1
    raise QueryError(f"unterminated string starting at position {start}")


def _date_literal(raw: str) -> Any:
    try:
        if "T" in raw:
            parts = raw.split("T")
            d = _dt.date.fromisoformat(parts[0])
            hh, mm, *rest = parts[1].split(":")
            ss = int(rest[0]) if rest else 0
            return _dt.datetime(d.year, d.month, d.day, int(hh), int(mm), ss)
        return _dt.date.fromisoformat(raw)
    except ValueError as exc:
        # e.g. 2026-13-40: shaped like a date, but not a real one.
        raise QueryError(f"invalid date literal {raw!r}: {exc}") from exc


# --- Parser ----------------------------------------------------------


class _Parser:
    def __init__(self, tokens: List[_Token], text: str) -> None:
        self.tokens = tokens
        self.text = text
        self.i = 0

    def peek(self) -> Optional[_Token]:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def next(self) -> _Token:
        token = self.peek()
        if token is None:
            raise QueryError("unexpected end of query")
        self.i += 1
        return token

    def at_keyword(self, *names: str) -> bool:
        token = self.peek()
        return token is not None and token.kind == "KW" and token.value in names

    def expect_keyword(self, name: str) -> None:
        token = self.next()
        if token.kind != "KW" or token.value != name:
            raise QueryError(f"expected {name}, got {token.value!r}")

    # clauses ---------------------------------------------------------

    def parse(self) -> Query:
        query = Query()
        if self.at_keyword("SELECT"):
            self.next()
            query.select = self._select_list()
        if self.at_keyword("FROM"):
            self.next()
            self._from_sources(query)
        if self.at_keyword("WHERE"):
            self.next()
            query.where = self._expr()
        if self.at_keyword("SORT"):
            self.next()
            query.sort = self._sort_list()
        if self.at_keyword("LIMIT"):
            self.next()
            query.limit = self._limit()
        leftover = self.peek()
        if leftover is not None:
            raise QueryError(
                f"unexpected {leftover.value!r} at position {leftover.pos}"
            )
        return query

    def _select_list(self) -> Optional[List[str]]:
        if self.peek() is not None and self.peek().kind == "STAR":
            self.next()
            return None  # SELECT * == no projection
        fields = [self._field_name("SELECT")]
        while self.peek() is not None and self.peek().kind == "COMMA":
            self.next()
            fields.append(self._field_name("SELECT"))
        return fields

    def _from_sources(self, query: Query) -> None:
        while True:
            token = self.next()
            if token.kind == "STR":
                query.folders.append(token.value.strip("/"))
            elif token.kind == "TAG":
                query.from_tags.append(token.value)
            else:
                raise QueryError(
                    'FROM expects a quoted folder ("projects") or a #tag'
                )
            if self.peek() is not None and self.peek().kind == "COMMA":
                self.next()
                continue
            break

    def _sort_list(self) -> List[Tuple[str, bool]]:
        keys = [self._sort_key()]
        while self.peek() is not None and self.peek().kind == "COMMA":
            self.next()
            keys.append(self._sort_key())
        return keys

    def _sort_key(self) -> Tuple[str, bool]:
        name = self._field_name("SORT")
        desc = False
        if self.at_keyword("ASC", "DESC"):
            desc = self.next().value == "DESC"
        return name, desc

    def _limit(self) -> int:
        token = self.next()
        if token.kind != "NUM" or not isinstance(token.value, int) or token.value < 1:
            raise QueryError("LIMIT expects a positive integer")
        return token.value

    def _field_name(self, clause: str) -> str:
        token = self.next()
        if token.kind == "IDENT":
            return token.value
        if token.kind == "STR":
            return token.value  # quoted field names may contain spaces
        raise QueryError(f"{clause} expects a field name, got {token.value!r}")

    # expressions -----------------------------------------------------

    def _expr(self) -> Expr:
        left = self._and()
        while self.at_keyword("OR"):
            self.next()
            left = Or(left, self._and())
        return left

    def _and(self) -> Expr:
        left = self._unary()
        while self.at_keyword("AND"):
            self.next()
            left = And(left, self._unary())
        return left

    def _unary(self) -> Expr:
        if self.at_keyword("NOT"):
            self.next()
            return Not(self._unary())
        return self._comparison()

    def _comparison(self) -> Expr:
        left = self._primary()
        token = self.peek()
        if token is None:
            return left
        if token.kind == "OP":
            self.next()
            return Cmp(token.value, left, self._primary())
        if token.kind == "KW" and token.value in ("CONTAINS", "IN", "MATCHES"):
            self.next()
            return Cmp(token.value.lower(), left, self._primary())
        return left

    def _primary(self) -> Expr:
        token = self.next()
        if token.kind == "LPAREN":
            inner = self._expr()
            closing = self.next()
            if closing.kind != "RPAREN":
                raise QueryError("expected ')'")
            return inner
        if token.kind == "LBRACKET":
            return Lit(self._list_literal())
        if token.kind == "STR":
            return Lit(token.value)
        if token.kind == "NUM":
            return Lit(token.value)
        if token.kind == "DATE":
            return Lit(_date_literal(token.value))
        if token.kind == "TAG":
            # "#tag" as an expression means "note has this tag".
            return Cmp("contains", Field("tags"), Lit(token.value))
        if token.kind == "KW" and token.value == "TRUE":
            return Lit(True)
        if token.kind == "KW" and token.value == "FALSE":
            return Lit(False)
        if token.kind == "KW" and token.value == "NULL":
            return Lit(None)
        if token.kind == "IDENT":
            return Field(token.value)
        raise QueryError(
            f"unexpected {token.value!r} at position {token.pos}"
        )

    def _list_literal(self) -> List[Any]:
        """A bracketed list of literals, e.g. ["open", "blocked", 3]."""
        items: List[Any] = []
        token = self.peek()
        if token is not None and token.kind == "RBRACKET":
            self.next()
            return items
        while True:
            token = self.next()
            if token.kind == "STR" or token.kind == "NUM":
                items.append(token.value)
            elif token.kind == "DATE":
                items.append(_date_literal(token.value))
            elif token.kind == "KW" and token.value in ("TRUE", "FALSE", "NULL"):
                items.append({"TRUE": True, "FALSE": False, "NULL": None}[token.value])
            else:
                raise QueryError(
                    f"expected a literal in list, got {token.value!r}"
                )
            closing = self.next()
            if closing.kind == "RBRACKET":
                return items
            if closing.kind != "COMMA":
                raise QueryError("expected ',' or ']' in list literal")


def parse_query(text: str) -> Query:
    """Parse a query string into a :class:`Query`.

    An empty string is a valid query matching every note.
    """
    return _Parser(_tokenize(text), text).parse()
