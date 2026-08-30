"""SpaceClaim / Discovery script linter (.scscript, .py).

Coverage model:

- *Exact/structural*: Python syntax (AST).
- *Heuristic*: product/API signature detection (``SpaceClaim.Api.VNN``
  references, ``Window.ActiveWindow``, ViewHelper blocks), API-version
  header mismatch notes, interactive-selection dependency warnings,
  path portability.

No claim is made that generic Python validation proves SpaceClaim API
validity (see docs/coverage.md).
"""

from __future__ import annotations

import ast
import re

from ..model import Confidence, Diagnostic, LintOptions, Severity
from ..rules_common import scan_path_literal
from ..textlines import LineIndex

API_VERSION_RE = re.compile(r"SpaceClaim\.Api\.V(\d+)")
# Recorded Discovery/SpaceClaim journals start with a header such as
# "# Python Script, API Version = V252".
DISCOVERY_HEADER_RE = re.compile(r"Python Script,\s*API Version\s*=\s*V\d+", re.IGNORECASE)
SIGNATURES = (
    "SpaceClaim.Api",
    "Window.ActiveWindow",
    "ViewHelper",
    "Document.Save",
    "Model.",
    "Selection.",
    "GetRootPart",
    "GetRoot",
)
INTERACTIVE_TOKENS = (
    "Window.ActiveWindow",
    "GetActiveObject",
    "ActiveEditor",
)


def lint(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    lines = LineIndex(text)

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        diagnostics.append(
            Diagnostic(
                code="PYTHON_SYNTAX_ERROR",
                severity=Severity.ERROR,
                message=f"SpaceClaim/Discovery script has a Python syntax error: {exc.msg}",
                line=exc.lineno or 1,
                column=exc.offset or 1,
                product="spaceclaim",
                dialect="spaceclaim-python",
                detected_version=options.target_version,
                file_path=file_path,
                explanation="The script must parse as Python before deeper checks can run.",
                suggested_fix="Fix the reported syntax error.",
                confidence=Confidence.HIGH,
                is_heuristic=False,
            )
        )
        return diagnostics

    # API version references.
    api_versions = API_VERSION_RE.findall(text)
    if len(set(api_versions)) > 1:
        first_line = next(
            i
            for i in range(1, lines.line_count + 1)
            if API_VERSION_RE.search(lines.line_text(i))
        )
        diagnostics.append(
            Diagnostic(
                code="SC_API_VERSION_MIXED",
                severity=Severity.WARNING,
                message=f"Script mixes SpaceClaim API versions: {', '.join(sorted(set(api_versions)))}.",
                line=first_line,
                product="spaceclaim",
                dialect="spaceclaim-python",
                detected_version=options.target_version,
                file_path=file_path,
                explanation="Recorded blocks from different API generations can conflict at runtime.",
                suggested_fix="Align clr.AddReference versions across the whole script.",
                confidence=Confidence.MEDIUM,
                is_heuristic=True,
            )
        )

    # Interactive-selection dependencies in unattended runs.
    if options.exec_mode.value != "interactive":
        for token in INTERACTIVE_TOKENS:
            position = text.find(token)
            if position >= 0:
                diagnostics.append(
                    Diagnostic(
                        code="SC_INTERACTIVE_DEPENDENCY",
                        severity=Severity.WARNING,
                        message=f"'{token}' depends on the interactive editor state.",
                        line=text.count("\n", 0, position) + 1,
                        product="spaceclaim",
                        dialect="spaceclaim-python",
                        detected_version=options.target_version,
                        file_path=file_path,
                        explanation=(
                            "Recording blocks replay selections against the currently "
                            "open document; batch execution may find nothing selected."
                        ),
                        suggested_fix="Resolve objects explicitly instead of relying on active selection.",
                        confidence=Confidence.MEDIUM,
                        is_heuristic=True,
                    )
                )
                break

    # Portability of string constants.
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for finding in scan_path_literal(
                node.value,
                target_os=options.target_os,
                line=node.lineno or 1,
                column=node.col_offset + 1,
                label="string literal",
            ):
                diagnostics.append(
                    Diagnostic(
                        code=finding.code,
                        severity=finding.severity,
                        message=finding.message,
                        line=node.lineno or 1,
                        column=node.col_offset + 1,
                        product="spaceclaim",
                        dialect="spaceclaim-python",
                        detected_version=options.target_version,
                        file_path=file_path,
                        explanation=finding.explanation,
                        suggested_fix=finding.suggested_fix,
                        confidence=finding.confidence,
                        is_heuristic=finding.is_heuristic,
                    )
                )

    return diagnostics


def signature_score(file_name: str, text: str) -> tuple[float, list[str]]:
    score = 0.0
    evidence: list[str] = []
    if file_name.lower().endswith(".scscript"):
        score += 0.6
        evidence.append("extension .scscript")
    if DISCOVERY_HEADER_RE.search(text[:400]):
        score += 0.45
        evidence.append("Discovery/SpaceClaim API version header")
    api_hit = bool(API_VERSION_RE.search(text))
    if api_hit:
        score += 0.35
        evidence.append("SpaceClaim.Api version reference")
    hits = sum(1 for sig in SIGNATURES if sig in text)
    if hits >= 2:
        score += 0.25
        evidence.append(f"{hits} product signatures")
    elif hits == 1:
        score += 0.1
        evidence.append("1 product signature")
    return min(score, 0.99), evidence
