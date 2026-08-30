"""Ansys Electronics Desktop (AEDT/HFSS/Maxwell/Twin Builder) linter.

Coverage model:

- *Exact/structural*: Python syntax (AST), VBScript block pairing.
- *Heuristic*: AEDT signature detection (``oDesktop``/``oProject``/
  ``oDesign``), local-COM / Windows-only dependency warnings, GUI-only
  call warnings in unattended runs.

Detection comes first; only structural and portability diagnostics are
emitted - no exact API validation is claimed (see docs/coverage.md).
"""

from __future__ import annotations

import ast
import re

from ..jscript import lint_vbscript
from ..model import Confidence, Diagnostic, LintOptions, Severity, TargetOS
from ..rules_common import scan_path_literal
from ..textlines import LineIndex

AEDT_SIGNATURES = ("oDesktop", "oProject", "oDesign", "oEditor", "oModule")
COM_IMPORTS = ("win32com", "comtypes", "pythoncom")
GUI_ONLY_CALLS = ("RestoreWindow",)
COM_OBJECT_RE = re.compile(r"NewObject\(|GetObject\(,")


def lint(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
    kind: str = "python",
) -> list[Diagnostic]:
    if kind == "vbscript":
        return _lint_vbs(text, options, file_path=file_path)
    return _lint_python(text, options, file_path=file_path)


def _lint_python(
    text: str,
    options: LintOptions,
    *,
    file_path: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        diagnostics.append(
            Diagnostic(
                code="PYTHON_SYNTAX_ERROR",
                severity=Severity.ERROR,
                message=f"AEDT script has a Python syntax error: {exc.msg}",
                line=exc.lineno or 1,
                column=exc.offset or 1,
                product="aedt",
                dialect="aedt-python",
                detected_version=options.target_version,
                file_path=file_path,
                explanation="The script must parse as Python before deeper checks can run.",
                suggested_fix="Fix the reported syntax error.",
                confidence=Confidence.HIGH,
                is_heuristic=False,
            )
        )
        return diagnostics

    # Local COM dependency.
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    com_hits = imports.intersection(COM_IMPORTS)
    if com_hits:
        severity = Severity.WARNING
        if options.target_os is TargetOS.LINUX:
            severity = Severity.WARNING
        diagnostics.append(
            Diagnostic(
                code="PORTABILITY_COM_DEPENDENCY",
                severity=severity,
                message=f"Script depends on local COM automation ({', '.join(sorted(com_hits))}).",
                line=1,
                product="aedt",
                dialect="aedt-python",
                detected_version=options.target_version,
                file_path=file_path,
                explanation=(
                    "COM automation attaches to a locally installed Windows desktop; "
                    "it cannot run on Linux compute nodes."
                ),
                suggested_fix="Run AEDT automation on a Windows client or via documented remote APIs.",
                confidence=Confidence.MEDIUM,
                is_heuristic=True,
            )
        )

    # GUI-only calls in unattended runs.
    if options.exec_mode.value != "interactive":
        lines = LineIndex(text)
        for token in GUI_ONLY_CALLS:
            for index in range(1, lines.line_count + 1):
                line = lines.line_text(index)
                if token in line:
                    diagnostics.append(
                        Diagnostic(
                            code="AEDT_GUI_ONLY_CALL",
                            severity=Severity.INFO,
                            message=f"'{token}' manipulates desktop window state and has no effect headless.",
                            line=index,
                            product="aedt",
                            dialect="aedt-python",
                            detected_version=options.target_version,
                            file_path=file_path,
                            explanation="Window-state calls assume an interactive desktop session.",
                            suggested_fix="Remove window-state calls from batch scripts.",
                            confidence=Confidence.LOW,
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
                        product="aedt",
                        dialect="aedt-python",
                        detected_version=options.target_version,
                        file_path=file_path,
                        explanation=finding.explanation,
                        suggested_fix=finding.suggested_fix,
                        confidence=finding.confidence,
                        is_heuristic=finding.is_heuristic,
                    )
                )
    return diagnostics


def _lint_vbs(
    text: str,
    options: LintOptions,
    *,
    file_path: str,
) -> list[Diagnostic]:
    diags = lint_vbscript(
        text,
        options,
        file_path=file_path,
        product="aedt",
        dialect="aedt-vbscript",
    )
    lowered = text.lower()
    if any(sig.lower() in lowered for sig in AEDT_SIGNATURES) and COM_OBJECT_RE.search(text):
        pass  # detection only; no fabricated API diagnostics
    return diags


def signature_score(file_name: str, text: str) -> tuple[float, list[str]]:
    score = 0.0
    evidence: list[str] = []
    hits = sum(1 for sig in AEDT_SIGNATURES if sig in text)
    if hits >= 2:
        score += 0.5 + 0.05 * min(hits, 6)
        evidence.append(f"{hits} o* object signatures")
    if any(module in text for module in COM_IMPORTS):
        score += 0.15
        evidence.append("COM import")
    if file_name.lower().endswith(".vbs") and hits >= 1:
        score += 0.2
        evidence.append(".vbs with oDesktop family")
    return min(score, 0.99), evidence
