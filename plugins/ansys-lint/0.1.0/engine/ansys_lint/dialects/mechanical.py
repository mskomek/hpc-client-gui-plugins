"""Ansys Mechanical scripting linter (.py, legacy .js/.vbs/.mcr).

Coverage model:

- *Exact/structural*: outer Python syntax (AST), embedded APDL command
  snippets re-linted through the MAPDL parser with coordinates mapped
  back to the outer file, legacy VBScript/JScript block structure.
- *Heuristic*: Mechanical signature detection (``ExtAPI``, ``DataModel``,
  ``Quantity``, tree APIs), interactive-selection dependency warnings.

Generic Python syntax validation does NOT prove Mechanical API validity;
no official Mechanical command catalog ships with this plugin (see
docs/coverage.md). Known-API migration lists are intentionally absent
until backed by official evidence.
"""

from __future__ import annotations

import ast
import re

from ..embedded import LiteralExtractor
from ..jscript import lint_jscript, lint_vbscript
from ..model import Confidence, CoordMapper, Diagnostic, LintOptions, Severity
from ..rules_common import scan_path_literal
from ..textlines import LineIndex

MECH_SIGNATURES = (
    "ExtAPI",
    "DataModel",
    "Quantity",
    "Tree.Activate",
    "Ansys.ACT",
    "AddCommandSnippet",
)
INTERACTIVE_TOKENS = (
    "ExtAPI.SelectionManager",
    "GetActiveSelection",
    "Tree.Activate",
    "ActiveSelection",
)

# An APDL-ish line: short uppercase token then comma/space args.
_APDL_LINE_RE = re.compile(r"^\s*([A-Z]{1,8}[0-9]{0,2})(\s*,|\s+[A-Za-z0-9_%'\"]|$)")


def _looks_like_apdl(content: str) -> bool:
    lines = [line for line in content.splitlines() if line.strip()]
    if not lines:
        return False
    hits = sum(1 for line in lines if _APDL_LINE_RE.match(line))
    return hits >= max(1, len(lines) // 2)


def _add_simple(
    diagnostics: list[Diagnostic],
    *,
    code: str,
    severity: Severity,
    message: str,
    file_path: str,
    line: int | None,
    column: int | None = None,
    explanation: str = "",
    suggested_fix: str = "",
    confidence: Confidence = Confidence.MEDIUM,
    is_heuristic: bool = True,
) -> None:
    diagnostics.append(
        Diagnostic(
            code=code,
            severity=severity,
            message=message,
            line=line,
            column=column,
            product="mechanical",
            dialect="mechanical-python",
            detected_version="",
            file_path=file_path,
            explanation=explanation,
            suggested_fix=suggested_fix,
            confidence=confidence,
            is_heuristic=is_heuristic,
        )
    )


def lint_python(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        _add_simple(
            diagnostics,
            code="PYTHON_SYNTAX_ERROR",
            severity=Severity.ERROR,
            message=f"Mechanical script has a Python syntax error: {exc.msg}",
            file_path=file_path,
            line=exc.lineno or 1,
            column=exc.offset or 1,
            explanation="The script must parse as Python before deeper checks can run.",
            suggested_fix="Fix the reported syntax error.",
            confidence=Confidence.HIGH,
            is_heuristic=False,
        )
        return diagnostics

    # Signature evidence doubles as an honest coverage note when absent.
    unattended = options.exec_mode.value != "interactive"

    # Embedded APDL command snippets.
    extractor = LiteralExtractor(text)
    from . import mapdl as mapdl_module

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        content = node.value
        if len(content) < 4 or not _looks_like_apdl(content):
            continue
        span = extractor.from_constant(node)
        if span is None:
            continue

        def make_mapper(sp=span):
            def map_line_col(inner_line: int, inner_column: int) -> tuple[int, int]:
                pos = sp.outer(inner_line, inner_column)
                return pos if pos else (node.lineno or 1, node.col_offset + 1)

            return CoordMapper(map_line_col=map_line_col, note=f"(APDL snippet at outer line {node.lineno})")

        mapped = []
        raw = mapdl_module.lint(content, options, file_path=file_path)
        mapper = make_mapper()
        note = f" {mapper.note}" if mapper.note else ""
        for diag in raw:
            new_line = new_col = None
            if diag.line is not None:
                new_line, new_col = mapper.map_line_col(diag.line, diag.column or 1)
            mapped.append(
                Diagnostic(
                    code=diag.code,
                    severity=diag.severity,
                    message=(diag.message + note).strip(),
                    line=new_line,
                    column=new_col,
                    end_line=diag.end_line,
                    end_column=diag.end_column,
                    confidence=diag.confidence,
                    product=diag.product,
                    dialect=f"apdl-snippet:{diag.dialect}",
                    detected_version=diag.detected_version,
                    supported_versions=diag.supported_versions,
                    file_path=file_path,
                    explanation=diag.explanation,
                    suggested_fix=diag.suggested_fix,
                    source_id=diag.source_id,
                    source_url=diag.source_url,
                    source_title=diag.source_title,
                    is_heuristic=diag.is_heuristic,
                )
            )
        diagnostics.extend(mapped)

    # Interactive-selection dependencies in unattended runs.
    if unattended:
        for token in INTERACTIVE_TOKENS:
            if token in text:
                _find = text.find(token)
                line_no = text.count("\n", 0, _find) + 1 if _find >= 0 else 1
                _add_simple(
                    diagnostics,
                    code="MECH_INTERACTIVE_SELECTION",
                    severity=Severity.WARNING,
                    message=f"'{token}' depends on the interactive tree/selection state.",
                    file_path=file_path,
                    line=line_no,
                    explanation=(
                        "Recorded selections resolve against the state of the open "
                        "Mechanical session; batch replays can silently act on the "
                        "wrong object or nothing at all."
                    ),
                    suggested_fix="Resolve objects by name/path instead of active selection.",
                    confidence=Confidence.MEDIUM,
                    is_heuristic=True,
                )
                break

    return diagnostics


def lint_legacy(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
    kind: str = "jscript",
) -> list[Diagnostic]:
    """Legacy Mechanical macros: JScript or VBScript recordings."""
    if kind == "vbscript":
        return lint_vbscript(
            text,
            options,
            file_path=file_path,
            product="mechanical",
            dialect="mechanical-vbscript",
        )
    diags, literals = lint_jscript(
        text,
        options,
        file_path=file_path,
        product="mechanical",
        dialect="mechanical-jscript",
    )
    lines = LineIndex(text)
    for value, inner_line, inner_col in literals:
        for finding in scan_path_literal(
            value,
            target_os=options.target_os,
            line=inner_line,
            column=inner_col,
            label="string literal",
        ):
            diags.append(
                Diagnostic(
                    code=finding.code,
                    severity=finding.severity,
                    message=finding.message,
                    line=inner_line,
                    column=inner_col,
                    product="mechanical",
                    dialect="mechanical-jscript",
                    detected_version=options.target_version,
                    file_path=file_path,
                    explanation=finding.explanation,
                    suggested_fix=finding.suggested_fix,
                    confidence=finding.confidence,
                    is_heuristic=finding.is_heuristic,
                )
            )
    del lines
    return diags


def lint(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
    kind: str = "python",
) -> list[Diagnostic]:
    if kind == "python":
        return lint_python(text, options, file_path=file_path)
    return lint_legacy(text, options, file_path=file_path, kind=kind)
