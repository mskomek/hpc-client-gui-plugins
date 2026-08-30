"""Ansys Motion journal linter (.dfjnl - XML).

Coverage model:

- *Exact*: XML well-formedness (parser-reported line/column).
- *Structural/heuristic*: operation elements missing obvious identity
  attributes, external file references and their path portability.

Motion validation is labelled structural unless a complete operation
schema becomes available (see docs/coverage.md).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from ..model import Confidence, Diagnostic, LintOptions, Severity
from ..rules_common import scan_path_literal

FILE_SUFFIXES = (
    ".stl",
    ".step",
    ".stp",
    ".igs",
    ".iges",
    ".mtd",
    ".dfjnl",
    ".xml",
    ".csv",
    ".txt",
)
IDENTITY_ATTRS = ("Name", "name", "Type", "type", "Id", "ID", "id")


def lint(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        line, column = exc.position
        diagnostics.append(
            Diagnostic(
                code="MOTION_XML_MALFORMED",
                severity=Severity.ERROR,
                message=f"Motion journal is not well-formed XML: {exc.msg}",
                line=line,
                column=column,
                product="motion",
                dialect="motion-xml",
                detected_version=options.target_version,
                file_path=file_path,
                explanation="The .dfjnl format is XML; a parse error means the journal cannot replay.",
                suggested_fix="Fix the XML syntax at the reported position.",
                confidence=Confidence.HIGH,
                is_heuristic=False,
            )
        )
        return diagnostics

    def walk(element: ET.Element) -> None:
        tag = element.tag or ""
        attribs = element.attrib

        # Operation-ish elements must identify themselves.
        if "operation" in tag.lower() and not any(attr in attribs for attr in IDENTITY_ATTRS):
            diagnostics.append(
                Diagnostic(
                    code="MOTION_OPERATION_ATTR_MISSING",
                    severity=Severity.WARNING,
                    message=f"<{tag}> records an operation without an identifying attribute.",
                    line=None,
                    product="motion",
                    dialect="motion-xml",
                    detected_version=options.target_version,
                    file_path=file_path,
                    explanation=(
                        "Operation entries normally carry a name/type attribute; "
                        "without one the entry cannot be matched to a documented "
                        "operation. Structural check only - no full schema ships."
                    ),
                    suggested_fix="Re-record the journal entry so it carries its name/type.",
                    confidence=Confidence.LOW,
                    is_heuristic=True,
                )
            )

        # External file references + portability.
        for attr_name, value in attribs.items():
            if not value:
                continue
            lowered_value = value.lower()
            if any(lowered_value.endswith(suffix) for suffix in FILE_SUFFIXES) and (
                "/" in value or "\\" in value or "." in value
            ):
                diagnostics.append(
                    Diagnostic(
                        code="MOTION_EXTERNAL_FILE_REF",
                        severity=Severity.INFO,
                        message=f"<{tag} {attr_name}='{value}'> references an external file.",
                        line=None,
                        product="motion",
                        dialect="motion-xml",
                        detected_version=options.target_version,
                        file_path=file_path,
                        explanation=(
                            "External references must exist on every machine that "
                            "replays the journal."
                        ),
                        confidence=Confidence.MEDIUM,
                        is_heuristic=True,
                    )
                )
                for finding in scan_path_literal(
                    value,
                    target_os=options.target_os,
                    line=1,
                    column=1,
                    label=f"{attr_name} reference",
                ):
                    diagnostics.append(
                        Diagnostic(
                            code=finding.code,
                            severity=finding.severity,
                            message=finding.message,
                            line=None,
                            product="motion",
                            dialect="motion-xml",
                            detected_version=options.target_version,
                            file_path=file_path,
                            explanation=finding.explanation,
                            suggested_fix=finding.suggested_fix,
                            confidence=finding.confidence,
                            is_heuristic=finding.is_heuristic,
                        )
                    )

        for child in element:
            walk(child)

    walk(root)
    return diagnostics


def signature_score(file_name: str, text: str) -> tuple[float, list[str]]:
    score = 0.0
    evidence: list[str] = []
    if file_name.lower().endswith(".dfjnl"):
        score += 0.8
        evidence.append("extension .dfjnl")
    elif text.lstrip().startswith("<?xml") or text.lstrip().startswith("<"):
        score += 0.15
        evidence.append("XML-looking content")
    return min(score, 0.99), evidence
