"""Aqwa JScript linter (embedded in Workbench SendCommand payloads).

No authoritative Aqwa command catalog ships with this plugin, so only
structural and portability diagnostics are provided. The linter makes no
claim of complete Aqwa API validation (see docs/coverage.md).
"""

from __future__ import annotations

from ..jscript import lint_jscript
from ..model import Diagnostic, LintOptions
from ..rules_common import scan_path_literal


def lint(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
    mapper=None,
) -> list[Diagnostic]:
    diags, literals = lint_jscript(
        text,
        options,
        file_path=file_path,
        product="aqwa",
        dialect="aqwa-jscript",
        mapper=mapper,
    )
    for value, inner_line, inner_col in literals:
        for finding in scan_path_literal(
            value,
            target_os=options.target_os,
            line=inner_line,
            column=inner_col,
            label="string literal",
        ):
            out_line, out_col = (
                mapper.map_line_col(inner_line, inner_col) if mapper else (inner_line, inner_col)
            )
            diags.append(
                Diagnostic(
                    code=finding.code,
                    severity=finding.severity,
                    message=finding.message,
                    line=out_line,
                    column=out_col,
                    product="aqwa",
                    dialect="aqwa-jscript",
                    detected_version=options.target_version,
                    file_path=file_path,
                    explanation=finding.explanation,
                    suggested_fix=finding.suggested_fix,
                    confidence=finding.confidence,
                    is_heuristic=finding.is_heuristic,
                )
            )
    return diags


def signature_score(file_name: str, text: str) -> tuple[float, list[str]]:
    """Aqwa detection relies on Workbench container context; standalone
    signature scoring stays deliberately weak."""
    return 0.1, []
