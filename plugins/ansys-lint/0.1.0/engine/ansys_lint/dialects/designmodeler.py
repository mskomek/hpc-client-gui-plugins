"""DesignModeler journal linter (.js, JScript + agb.* API).

Coverage model:

- *Exact/structural*: JScript bracket/string balance, version header
  parsing.
- *Heuristic*: agb.* API usage evidence, hard-coded paths, release
  assumptions between the recorded header version and the selected
  target.

DesignModeler API rules stay separate from generic browser-JavaScript
rules: no web-oriented checks are applied here.
"""

from __future__ import annotations

import re

from ..jscript import lint_jscript
from ..model import Confidence, Diagnostic, LintOptions, Severity
from ..rules_common import scan_path_literal
from ..textlines import LineIndex

HEADER_RE = re.compile(r"DesignModeler\s+Script.*?(?:Version\s*:?\s*)?(\d+[.\d]*)", re.IGNORECASE)
AGB_RE = re.compile(r"\bagb\.\w+")


def lint(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    lines = LineIndex(text)

    diags, literals = lint_jscript(
        text,
        options,
        file_path=file_path,
        product="designmodeler",
        dialect="designmodeler-jscript",
    )
    diagnostics.extend(diags)

    # Version header.
    head_text = "\n".join(lines.line_text(i) for i in range(1, min(6, lines.line_count + 1)))
    header_match = HEADER_RE.search(head_text)
    if header_match:
        declared = header_match.group(1).rstrip(".")
        target_major = options.target_version.split(".")[0]
        declared_major = declared.split(".")[0]
        if declared_major and target_major and declared_major != target_major:
            try:
                if abs(float(declared_major) - float(target_major)) >= 10:
                    diagnostics.append(
                        Diagnostic(
                            code="DM_VERSION_HEADER_MISMATCH",
                            severity=Severity.INFO,
                            message=f"Script was recorded for DesignModeler {declared}; selected target is {options.target_version}.",
                            line=1,
                            product="designmodeler",
                            dialect="designmodeler-jscript",
                            detected_version=options.target_version,
                            file_path=file_path,
                            explanation=(
                                "Recorded agb.* scripts can change behaviour across major "
                                "releases; verify against your installed release."
                            ),
                            suggested_fix="Re-record or review the script for the installed release.",
                            confidence=Confidence.LOW,
                            is_heuristic=True,
                        )
                    )
            except ValueError:
                pass

    # agb usage evidence / absence note.
    agb_hits = AGB_RE.findall(text)
    if not agb_hits and text.strip():
        first_line = lines.line_text(1).strip() if lines.line_count else ""
        diagnostics.append(
            Diagnostic(
                code="DM_NO_AGB_USAGE",
                severity=Severity.INFO,
                message="No agb.* API calls found; this may not be a DesignModeler journal.",
                line=1 if not first_line else None,
                product="designmodeler",
                dialect="designmodeler-jscript",
                detected_version=options.target_version,
                file_path=file_path,
                explanation=(
                    "DesignModeler journals drive geometry through the agb.* scripting "
                    "API. Files without any agb call are usually ordinary JavaScript."
                ),
                suggested_fix="Select a different dialect if this file is not a DM journal.",
                confidence=Confidence.MEDIUM,
                is_heuristic=True,
            )
        )

    # Portability of string literals.
    for value, inner_line, inner_col in literals:
        for finding in scan_path_literal(
            value,
            target_os=options.target_os,
            line=inner_line,
            column=inner_col,
            label="string literal",
        ):
            diagnostics.append(
                Diagnostic(
                    code=finding.code,
                    severity=finding.severity,
                    message=finding.message,
                    line=inner_line,
                    column=inner_col,
                    product="designmodeler",
                    dialect="designmodeler-jscript",
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
    if file_name.lower().endswith(".js"):
        score += 0.2
        evidence.append("extension .js")
    if HEADER_RE.search(text[:400]):
        score += 0.5
        evidence.append("DesignModeler script header")
    hits = AGB_RE.findall(text)
    if len(hits) >= 2:
        score += 0.35
        evidence.append(f"{len(hits)} agb.* calls")
    return min(score, 0.99), evidence
