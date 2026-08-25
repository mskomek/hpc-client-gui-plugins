"""Structural JScript / VBScript / legacy-JavaScript checks.

DesignModeler journals, Aqwa SendCommand payloads and legacy Mechanical
macros are JScript or VBScript. This module performs honest *structural*
validation only - bracket balance, string termination and VBScript block
pairing. It makes NO claim about the validity of product API calls
(agb.*, oDesktop, ...); those are detection/usage signals only.
"""

from __future__ import annotations

import re

from .model import Confidence, CoordMapper, Diagnostic, LintOptions, Severity
from .textlines import LineIndex

_PAIRS = {")": "(", "]": "[", "}": "{"}


def _diag(
    diagnostics: list[Diagnostic],
    lines: LineIndex,
    *,
    code: str,
    severity: Severity,
    message: str,
    offset: int,
    file_path: str,
    product: str,
    dialect: str,
    explanation: str = "",
    suggested_fix: str = "",
    confidence: Confidence = Confidence.HIGH,
    is_heuristic: bool = False,
    mapper: CoordMapper | None = None,
) -> None:
    line, column = lines.line_col(offset)
    out_line, out_col = line, column
    note = ""
    if mapper is not None:
        out_line, out_col = mapper.map_line_col(line, column)
        note = f" {mapper.note}" if mapper.note else ""
    diagnostics.append(
        Diagnostic(
            code=code,
            severity=severity,
            message=message + note.rstrip(),
            line=out_line,
            column=out_col,
            product=product,
            dialect=dialect,
            file_path=file_path,
            explanation=explanation,
            suggested_fix=suggested_fix,
            confidence=confidence,
            is_heuristic=is_heuristic,
        )
    )


def _scan_js(
    text: str,
) -> tuple[list[tuple[str, int, int]], list[tuple[str, int]]]:
    """Single-pass JS scanner.

    Returns:
        issues: list of (code, message, absolute_offset)
        literals: list of (string_value, absolute_offset_of_open_quote)
    """
    issues: list[tuple[str, int, int]] = []
    literals: list[tuple[str, int]] = []
    stack: list[str] = []
    i = 0
    n = len(text)
    # state stack entries: "tpl" inside template literal, "interp" inside ${ }
    states: list[str] = []

    def in_template_text() -> bool:
        return bool(states) and states[-1] == "tpl"

    while i < n:
        ch = text[i]

        if in_template_text():
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == "`":
                states.pop()
                i += 1
                continue
            if ch == "$" and i + 1 < n and text[i + 1] == "{":
                states.append("interp")
                stack.append("{")
                i += 2
                continue
            if ch == "\n":
                pass  # newlines are legal inside template text
            i += 1
            continue

        # comments
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            nl = text.find("\n", i)
            i = n if nl == -1 else nl + 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            if end == -1:
                issues.append(("JS_COMMENT_UNCLOSED", "'/*' comment is never closed.", i))
                break
            i = end + 2
            continue

        # strings
        if ch in ("'", '"'):
            j = i + 1
            value_chars: list[str] = []
            closed = False
            while j < n and text[j] != "\n":
                cj = text[j]
                if cj == "\\" and j + 1 < n:
                    value_chars.append(text[j : j + 2])
                    j += 2
                    continue
                if cj == ch:
                    closed = True
                    break
                value_chars.append(cj)
                j += 1
            if not closed:
                issues.append(
                    (
                        "JS_UNTERMINATED_STRING",
                        f"String literal starting at offset {i} is not terminated before the end of its line.",
                        i,
                    )
                )
                i = j + 1 if j < n else n
                continue
            literals.append(("".join(value_chars), i))
            i = j + 1
            continue
        if ch == "`":
            states.append("tpl")
            i += 1
            continue

        # brackets
        if ch in "([{":
            stack.append(ch)
            i += 1
            continue
        if ch in ")]}":
            if not stack:
                issues.append(("JS_UNBALANCED_BRACE", f"'{ch}' closes nothing.", i))
            else:
                opener = stack.pop()
                if opener != _PAIRS[ch]:
                    issues.append(
                        (
                            "JS_UNBALANCED_BRACE",
                            f"Mismatched bracket: '{ch}' closes '{opener}'.",
                            i,
                        )
                    )
            i += 1
            continue

        i += 1

    while states:
        state = states.pop()
        if state == "tpl":
            issues.append(("JS_TEMPLATE_UNCLOSED", "Template literal opened with a backtick is never closed.", n))

    while stack:
        opener = stack.pop()
        issues.append(
            (
                "JS_UNBALANCED_BRACE",
                f"'{opener}' is never closed.",
                max(n - 1, 0),
            )
        )

    return issues, literals


def lint_jscript(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
    product: str,
    dialect: str,
    mapper: CoordMapper | None = None,
) -> tuple[list[Diagnostic], list[tuple[str, int, int]]]:
    """Structural checks for JScript content.

    Returns (diagnostics, string_literals) where literals carry
    (value, outer_line, outer_column) so callers can run portability rules.
    """
    diagnostics: list[Diagnostic] = []
    lines = LineIndex(text)
    issues, raw_literals = _scan_js(text)
    for code, message, offset in issues:
        _diag(
            diagnostics,
            lines,
            code=code,
            severity=Severity.ERROR,
            message=message,
            offset=offset,
            file_path=file_path,
            product=product,
            dialect=dialect,
            explanation="Structural balance problems change how the whole script parses.",
            suggested_fix="Fix bracket/string termination before trusting further results.",
            mapper=mapper,
        )
    converted = [lines.line_col(offset) + (value,) for value, offset in raw_literals]
    literals = [(value, line, col) for (line, col, value) in converted]
    del raw_literals
    return diagnostics, literals


_VBS_BLOCK_RE = re.compile(r"^\s*(sub|function|if|for|do|select\s+case)\b(.*)$", re.IGNORECASE)


def lint_vbscript(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
    product: str,
    dialect: str,
    mapper: CoordMapper | None = None,
) -> list[Diagnostic]:
    """Pair-wise VBScript block check: Sub/End Sub, Function/End Function,
    block If/End If, For/Next, Do/Loop."""
    diagnostics: list[Diagnostic] = []
    lines = LineIndex(text)
    stack: list[tuple[str, int]] = []

    closers = {
        "sub": "End Sub",
        "function": "End Function",
        "if": "End If",
        "for": "Next",
        "do": "Loop",
        "select case": "End Select",
    }
    expected_closers = {
        "end sub": "sub",
        "end function": "function",
        "end if": "if",
        "next": "for",
        "loop": "do",
        "end select": "select case",
    }

    for index in range(1, lines.line_count + 1):
        raw = lines.line_text(index)
        stripped = raw.split("'", 1)[0].strip()
        if not stripped:
            continue
        lowered = re.sub(r"\s+", " ", stripped.lower())

        match = _VBS_BLOCK_RE.match(stripped)
        if match:
            keyword = re.sub(r"\s+", " ", match.group(1).lower())
            rest = match.group(2).strip().lower()
            if keyword == "if" and rest.startswith("then") and len(rest) > 4:
                continue  # single-line If ... Then <stmt>
            stack.append((keyword, index))
            continue

        closer_kind = None
        for token, kind in expected_closers.items():
            if lowered == token or lowered.startswith(token + " ") or lowered.startswith(token + ":"):
                closer_kind = kind
                break
        if closer_kind is None:
            continue  # Else/ElseIf/ Wend etc. stay within their block
        if not stack or stack[-1][0] != closer_kind:
            closer_name = next(
                (token for token, kind in expected_closers.items() if kind == closer_kind),
                closer_kind,
            )
            _diag(
                diagnostics,
                lines,
                code="VBS_UNBALANCED_BLOCK",
                severity=Severity.ERROR,
                message=f"Block terminator '{closer_name}' without a matching opener.",
                offset=lines.offset(index, len(raw) - len(stripped) + 1),
                file_path=file_path,
                product=product,
                dialect=dialect,
                suggested_fix=f"Remove '{closer_name}' or add its matching opener.",
                mapper=mapper,
            )
        else:
            stack.pop()

    for kind, opening_line in stack:
        closer_name = closers.get(kind, "End")
        _diag(
            diagnostics,
            lines,
            code="VBS_UNBALANCED_BLOCK",
            severity=Severity.ERROR,
            message=f"'{kind}' block opened here is never closed ('{closer_name}' missing).",
            offset=lines.offset(opening_line, 1),
            file_path=file_path,
            product=product,
            dialect=dialect,
            suggested_fix=f"Add '{closer_name}'.",
            mapper=mapper,
        )

    return diagnostics
