"""Extraction of embedded-language payloads from Python sources.

Workbench journals pass native commands to integrated applications through
``SendCommand(Command="...", Language="...")``. This module decodes string
literals (including escaped sequences and implicitly concatenated parts)
while keeping a per-character map back into the original source so nested
diagnostics can be reported at the correct OUTER file line/column.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

_LITERAL_PREFIX_RE = re.compile(r"^([A-Za-z]{0,2})(\"\"\"|'''|\"|')")
_TRIPLE_QUOTES = {'"""': '"""', "'''": "'''"}


@dataclass(frozen=True)
class LiteralSpan:
    """Decoded literal value plus a map back into the original text."""

    value: str
    offsets: tuple[int, ...]  # per decoded character: absolute source offset
    start_line: int
    start_column: int

    def decoded_index(self, inner_line: int, inner_column: int) -> int | None:
        """Index into ``value`` for 1-based inner (line, column)."""
        starts = [0]
        for pos, ch in enumerate(self.value):
            if ch == "\n":
                starts.append(pos + 1)
        if inner_line < 1 or inner_line > len(starts):
            return None
        index = starts[inner_line - 1] + max(inner_column - 1, 0)
        if inner_line < len(starts):
            limit = starts[inner_line] - 1
        else:
            limit = len(self.value)
        if index > limit:
            return None
        return index

    def outer_position(self, inner_line: int, inner_column: int) -> tuple[int, int] | None:
        index = self.decoded_index(inner_line, inner_column)
        if index is None:
            return None
        return self._lookup(index)

    def _lookup(self, index: int) -> tuple[int, int]:  # pragma: no cover - superseded
        idx = min(index, len(self.offsets) - 1)
        return self.start_line, self.start_column + idx


@dataclass(frozen=True)
class LiteralSpanOffsetter:
    """Concrete span bound to one source text for coordinate conversion."""

    span: LiteralSpan
    line_starts: tuple[int, ...]

    def outer(self, inner_line: int, inner_column: int) -> tuple[int, int] | None:
        pos = self.span.decoded_index(inner_line, inner_column)
        if pos is None:
            return None
        offset = self.span.offsets[min(pos, len(self.span.offsets) - 1)]
        low, high = 0, len(self.line_starts) - 1
        while low < high:
            mid = (low + high + 1) // 2
            if self.line_starts[mid] <= offset:
                low = mid
            else:
                high = mid - 1
        return low + 1, offset - self.line_starts[low] + 1


def _decode_body(body: str, base_offset: int, raw_prefix: bool) -> tuple[str, list[int]]:
    """Decode a literal body; return value and absolute offset per char."""
    value_chars: list[str] = []
    offsets: list[int] = []
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        if ch != "\\" or raw_prefix:
            value_chars.append(ch)
            offsets.append(base_offset + i)
            i += 1
            continue
        # escape sequence
        if i + 1 >= n:
            value_chars.append("\\")
            offsets.append(base_offset + i)
            break
        nxt = body[i + 1]
        simple = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"', "a": "\a", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
        if nxt == "x" and i + 3 < n:
            try:
                code = int(body[i + 2 : i + 4], 16)
                value_chars.append(chr(code))
                offsets.append(base_offset + i + 2)
                i += 4
                continue
            except ValueError:
                pass
        if nxt == "u" and i + 5 < n:
            try:
                code = int(body[i + 2 : i + 6], 16)
                value_chars.append(chr(code))
                offsets.append(base_offset + i + 2)
                i += 6
                continue
            except ValueError:
                pass
        if nxt in "1234567":
            j = i + 1
            digits = ""
            while j < n and len(digits) < 3 and body[j] in "01234567":
                digits += body[j]
                j += 1
            value_chars.append(chr(int(digits, 8)))
            offsets.append(base_offset + i + 1)
            i += 1 + len(digits)
            continue
        if nxt in simple:
            value_chars.append(simple[nxt])
            offsets.append(base_offset + i + 1)
            i += 2
            continue
        # unknown escape: keep both characters (matches Python warning behavior loosely)
        value_chars.append(nxt)
        offsets.append(base_offset + i + 1)
        i += 2
    return "".join(value_chars), offsets


class LiteralExtractor:
    """Extracts string-literal spans from one parsed source text."""

    def __init__(self, text: str) -> None:
        self.text = text
        starts = [0]
        for pos, ch in enumerate(text):
            if ch == "\n":
                starts.append(pos + 1)
        self.line_starts = tuple(starts)

    def offset(self, line: int, column: int) -> int:
        line = max(line, 1)
        if line > len(self.line_starts):
            return len(self.text)
        return self.line_starts[line - 1] + max(column - 1, 0)

    def from_constant(self, node: ast.Constant) -> LiteralSpanOffsetter | None:
        if not isinstance(node.value, str):
            return None
        segment = ast.get_source_segment(self.text, node)
        if segment is None:
            return None
        match = _LITERAL_PREFIX_RE.match(segment)
        if match is None:
            return None
        prefix = match.group(1).lower()
        quote = match.group(2)
        body_start = match.end()
        if quote in _TRIPLE_QUOTES:
            end_quote_len = 3
        else:
            end_quote_len = 1
        body_end = len(segment) - end_quote_len
        if body_end < body_start:
            body_end = body_start
        body = segment[body_start:body_end]
        base = self.offset(node.lineno, node.col_offset + 1) + body_start
        value, offsets = _decode_body(body, base, "r" in prefix)
        span = LiteralSpan(
            value=value,
            offsets=tuple(offsets),
            start_line=node.lineno,
            start_column=node.col_offset + 1,
        )
        return LiteralSpanOffsetter(span, self.line_starts)

    def from_expression(self, node: ast.expr) -> LiteralSpanOffsetter | None:
        """Collect a plain constant or an implicit/explicit concatenation."""
        parts = self._flatten_concat(node)
        if not parts:
            return None
        spans = [self.from_constant(part) for part in parts]
        if any(span is None for span in spans):
            return None
        value_parts: list[str] = []
        offsets: list[int] = []
        for span in spans:
            assert span is not None
            value_parts.append(span.span.value)
            offsets.extend(span.span.offsets)
        first = spans[0].span
        combined = LiteralSpan(
            value="".join(value_parts),
            offsets=tuple(offsets),
            start_line=first.start_line,
            start_column=first.start_column,
        )
        return LiteralSpanOffsetter(combined, self.line_starts)

    def _flatten_concat(self, node: ast.expr) -> list[ast.Constant]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._flatten_concat(node.left)
            right = self._flatten_concat(node.right)
            return left + right
        return []


def iter_sendcommand_calls(tree: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            name = getattr(func, "attr", getattr(func, "id", ""))
            if isinstance(name, str) and name.lower().endswith("sendcommand"):
                calls.append(node)
            self.generic_visit(node)

    Visitor().visit(tree)
    return calls


def keyword_args(call: ast.Call) -> dict[str, ast.expr]:
    return {
        kw.arg: kw.value
        for kw in call.keywords
        if isinstance(kw.arg, str)
    }


def positional_strings(call: ast.Call) -> list[ast.Constant]:
    return [arg for arg in call.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
