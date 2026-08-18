"""A small, dependency-free HCL2-ish parser.

CloudPilot only needs the subset of HCL used by real-world Terraform modules:

* block definitions ``type "label" "label" { ... }``
* attributes ``key = value``
* single / double quoted strings (with ``${interpolation}`` preserved verbatim)
* numbers, booleans, ``null``
* lists ``[...]`` and maps ``{...}``
* comments: ``#``, ``//`` and ``/* ... */``
* heredocs ``<<EOF ... EOF`` and ``<<-EOF ... EOF``

Unknown syntax degrades gracefully: any unparseable attribute keeps its raw
text as a string so downstream consumers still see the value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

TokenKind = str

# Token kinds
IDENT = "ident"
STRING = "string"
NUMBER = "number"
PUNCT = "punct"
OP = "op"
EOF = "eof"


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    value: str
    line: int


@dataclass
class HCLAttribute:
    key: str
    value: Any
    raw: str
    line: int

    @property
    def as_string(self) -> str:
        """Best-effort string form of the attribute value."""
        if isinstance(self.value, str):
            return self.value
        if isinstance(self.value, bool):
            return "true" if self.value else "false"
        if self.value is None:
            return "null"
        return str(self.value)


@dataclass
class HCLBlock:
    type: str
    labels: list[str]
    attributes: list[HCLAttribute] = field(default_factory=list)
    blocks: list[HCLBlock] = field(default_factory=list)
    line: int = 0
    source: str = ""

    def attr(self, key: str) -> HCLAttribute | None:
        """Return the first attribute matching ``key`` or ``None``."""
        for a in self.attributes:
            if a.key == key:
                return a
        return None

    def attrs(self, key: str) -> list[HCLAttribute]:
        """Return all attributes matching ``key`` (repeated attributes)."""
        return [a for a in self.attributes if a.key == key]

    def children(self, block_type: str) -> list[HCLBlock]:
        """Return direct child blocks of a given type."""
        return [b for b in self.blocks if b.type == block_type]

    @property
    def resource_id(self) -> str:
        """Join type + labels into a stable identifier, e.g. ``aws_instance.web``."""
        return ".".join([self.type, *self.labels])

    def dump(self, indent: int = 0) -> str:
        pad = "  " * indent
        lines = [f"{pad}{self.type} {' '.join(repr(label) for label in self.labels)} {{"]
        for a in self.attributes:
            lines.append(f"{pad}  {a.key} = {a.raw}")
        for b in self.blocks:
            lines.append(b.dump(indent + 1))
        lines.append(f"{pad}}}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_NUMBER_RE = re.compile(r"-?\d+(\.\d+)?([eE][+-]?\d+)?")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
_PUNCT = set("{}[]=(),.")


def _tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(source)
    line = 1

    while i < n:
        ch = source[i]

        if ch == "\n":
            line += 1
            i += 1
            continue
        if ch in " \t\r":
            i += 1
            continue

        # Comments
        if source.startswith("//", i):
            while i < n and source[i] != "\n":
                i += 1
            continue
        if ch == "#":
            while i < n and source[i] != "\n":
                i += 1
            continue
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            if end == -1:
                break
            line += source.count("\n", i, end)
            i = end + 2
            continue

        # Strings
        if ch == '"':
            end = i + 1
            while end < n:
                if source[end] == "\\" and end + 1 < n:
                    end += 2
                    continue
                if source[end] == '"':
                    break
                end += 1
            raw = source[i : end + 1]
            value = raw[1:-1]
            tokens.append(Token(STRING, value, line))
            line += source.count("\n", i, end + 1)
            i = end + 1
            continue

        # Heredocs
        if source.startswith("<<", i):
            end_of_op = i + 2
            indent_flag = source[i + 2] == "-"
            if indent_flag:
                end_of_op = i + 3
            while end_of_op < n and source[end_of_op] not in "\r\n":
                end_of_op += 1
            marker = source[i + (3 if indent_flag else 2) : end_of_op].strip()
            term = "\n" + marker
            body_start = end_of_op + 1
            body_end = source.find(term, body_start)
            if body_end == -1:
                body_end = n
            value = source[body_start:body_end]
            tokens.append(Token(STRING, value, line))
            line += source.count("\n", i, body_end + len(marker) + 1)
            i = body_end + len(marker) + 1
            continue

        # Numbers
        if ch.isdigit() or (ch == "-" and i + 1 < n and source[i + 1].isdigit()):
            m = _NUMBER_RE.match(source, i)
            if m:
                raw = m.group(0)
                tokens.append(Token(NUMBER, raw, line))
                i += len(raw)
                continue

        # Identifiers
        if ch.isalpha() or ch == "_":
            m = _IDENT_RE.match(source, i)
            if m:
                tokens.append(Token(IDENT, m.group(0), line))
                i += len(m.group(0))
                continue

        # Punctuation / operators
        if ch in _PUNCT:
            tokens.append(Token(PUNCT, ch, line))
            i += 1
            continue
        if ch in ("=", "+", "-", "*", "/", "%", ">", "<", "!", "?", ":", "&&", "||"):
            two = source[i : i + 2]
            if two in ("==", "!=", ">=", "<=", "&&", "||", "=>", "->"):
                tokens.append(Token(PUNCT, two, line))
                i += 2
                continue
            tokens.append(Token(PUNCT, ch, line))
            i += 1
            continue

        # Skip anything unknown
        i += 1

    tokens.append(Token(EOF, "", line))
    return tokens


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    def _peek(self, offset: int = 0) -> Token:
        idx = min(self.pos + offset, len(self.tokens) - 1)
        return self.tokens[idx]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.kind != EOF:
            self.pos += 1
        return tok

    def _expect(self, value: str) -> Token:
        tok = self._advance()
        if tok.value != value:
            raise ValueError(f"Expected '{value}' but got '{tok.value}' at line {tok.line}")
        return tok

    def parse(self) -> list[HCLBlock]:
        blocks: list[HCLBlock] = []
        while self._peek().kind != EOF:
            if self._peek().value in ("}", "]"):
                self._advance()
                continue
            blocks.append(self._parse_block())
        return blocks

    def _parse_block(self) -> HCLBlock:
        type_tok = self._advance()
        block_type = type_tok.value
        labels: list[str] = []
        while self._peek().kind in (STRING, IDENT, NUMBER):
            labels.append(self._advance().value)
        if self._peek().value != "{":
            # Malformed block; consume until a '{' or EOF to avoid infinite loop.
            while self._peek().value not in ("{", "}", EOF):
                self._advance()
            if self._peek().value == "}":
                self._advance()
            return HCLBlock(type=block_type, labels=labels, line=type_tok.line)

        self._advance()  # consume '{'
        block = HCLBlock(type=block_type, labels=labels, line=type_tok.line)
        while True:
            tok = self._peek()
            if tok.value == "}":
                self._advance()
                break
            if tok.kind == EOF:
                break
            if tok.value in (
                "}",
                "]",
            ):
                self._advance()
                continue
            if tok.kind == IDENT and self._peek(1).value in ("{", "="):
                key_tok = self._advance()
                if self._peek().value == "=":
                    self._advance()  # '='
                    value, raw = self._parse_value()
                    block.attributes.append(
                        HCLAttribute(key=key_tok.value, value=value, raw=raw, line=key_tok.line)
                    )
                else:
                    # Nested block
                    self._expect("{")
                    nested = self._parse_inline_until("}")
                    nested.type = key_tok.value
                    block.blocks.append(nested)
            else:
                # Something unexpected — skip a token to make progress.
                self._advance()
        return block

    def _parse_inline_until(self, end_value: str) -> HCLBlock:
        start_line = self._peek().line
        nested = HCLBlock(type="__inline__", labels=[], line=start_line)
        while True:
            tok = self._peek()
            if tok.value == end_value or tok.kind == EOF:
                break
            if tok.kind == IDENT and self._peek(1).value == "=":
                key_tok = self._advance()
                self._advance()
                value, raw = self._parse_value()
                nested.attributes.append(
                    HCLAttribute(key=key_tok.value, value=value, raw=raw, line=key_tok.line)
                )
            else:
                self._advance()
        if self._peek().value == end_value:
            self._advance()
        return nested

    def _parse_value(self):
        """Parse a value starting at the current position.

        Returns ``(value, raw_text)``.
        """
        tok = self._peek()

        if tok.kind == STRING:
            self._advance()
            return tok.value, f'"{tok.value}"'

        if tok.kind == NUMBER:
            self._advance()
            try:
                return int(tok.value) if tok.value.isdigit() or tok.value.startswith(
                    "-"
                ) and tok.value[1:].isdigit() else float(tok.value), tok.value
            except ValueError:
                return float(tok.value), tok.value

        if tok.kind == IDENT:
            if tok.value in ("true", "false"):
                self._advance()
                return tok.value == "true", tok.value
            if tok.value == "null":
                self._advance()
                return None, tok.value
            # Bare reference e.g. aws_security_group.foo.id or var.name
            # Stop at whitespace/newline boundaries: references never span lines.
            raw_parts: list[str] = []
            start_line = tok.line
            while self._peek().line == start_line and (
                self._peek().kind in (IDENT, NUMBER) or self._peek().value == "."
            ):
                raw_parts.append(self._advance().value)
            return "".join(raw_parts), "".join(raw_parts)

        if tok.value == "[":
            start = self.pos
            self._advance()
            items: list[Any] = []
            while self._peek().value != "]":
                if self._peek().kind == EOF:
                    break
                if self._peek().value == ",":
                    self._advance()
                    continue
                if self._peek().value == "[":
                    value, _ = self._parse_value()
                    items.append(value)
                    continue
                if self._peek().value == "{":
                    # list of maps
                    self._advance()
                    m: dict[str, Any] = {}
                    while self._peek().value != "}":
                        if self._peek().kind == EOF:
                            break
                        if self._peek().kind == IDENT and self._peek(1).value == "=":
                            k = self._advance().value
                            self._advance()
                            v, _ = self._parse_value()
                            m[k] = v
                        else:
                            self._advance()
                    self._expect("}")
                    items.append(m)
                    continue
                value, _ = self._parse_value()
                items.append(value)
            self._expect("]")
            raw = "".join(t.value for t in self.tokens[start : self.pos])
            return items, raw

        if tok.value == "{":
            start = self.pos
            self._advance()
            m: dict[str, Any] = {}
            while self._peek().value != "}":
                if self._peek().kind == EOF:
                    break
                if self._peek().kind == IDENT and self._peek(1).value in ("=",):
                    k = self._advance().value
                    self._advance()
                    v, _ = self._parse_value()
                    m[k] = v
                else:
                    self._advance()
            self._expect("}")
            raw = "".join(t.value for t in self.tokens[start : self.pos])
            return m, raw

        if tok.value in ("(",):
            self._advance()
            value, raw = self._parse_value()
            if self._peek().value == ")":
                self._advance()
            return value, raw

        # Fallback: consume until a safe delimiter, always making progress so
        # callers can never spin on the same token.
        parts: list[str] = [self._advance().value]
        while self._peek().kind != EOF and self._peek().value not in ("}", "]", ",", ")"):
            parts.append(self._advance().value)
        raw = "".join(parts)
        return raw, raw


def parse_hcl(source: str) -> list[HCLBlock]:
    """Parse an HCL string into a list of top-level blocks.

    The parser never raises: malformed input degrades to ``raw`` attributes.
    """
    tokens = _tokenize(source)
    parser = _Parser(tokens)
    try:
        return parser.parse()
    except Exception:
        return []


def parse_hcl_file(path: str) -> list[HCLBlock]:
    """Parse an HCL file on disk."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return parse_hcl(fh.read())
