"""Ansys System Coupling script linter (``systemcoupling -R run.py``).

Coverage model:

- *Exact/structural*: outer-file Python syntax (AST), allocation-fraction
  arithmetic on literal values, presence/absence of structurally required
  calls once the file is identified as a System Coupling script.
- *Catalog-backed*: command names from the official settings/commands
  reference subset (AddParticipant, AddInterface, AddDataTransfer,
  DatamodelRoot, Initialize, Solve, Save, Open, Shutdown,
  PartitionParticipants).
- *Heuristic*: unknown coupling-style calls, hard-coded participant paths,
  portability warnings.

The linter never claims full API validation: only the shipped command
subset is checked by name.
"""

from __future__ import annotations

import ast
import re

from ..model import Confidence, CoordMapper, Diagnostic, LintOptions, Severity
from ..rules_common import scan_path_literal
from ..sources import resolve as source

SYSC_COMMANDS = {
    "addparticipant": {"source_id": "ansys-sysc-reference-25r2"},
    "addinterface": {"source_id": "ansys-sysc-reference-25r2"},
    "adddatatransfer": {"source_id": "ansys-sysc-reference-25r2"},
    "datamodelroot": {"source_id": "ansys-sysc-reference-25r2"},
    "initialize": {"source_id": "ansys-sysc-reference-25r2"},
    "solve": {"source_id": "ansys-sysc-reference-25r2"},
    "save": {"source_id": "ansys-sysc-reference-25r2"},
    "open": {"source_id": "ansys-sysc-reference-25r2"},
    "shutdown": {"source_id": "ansys-sysc-reference-25r2"},
    "partitionparticipants": {"source_id": "ansys-sysc-hpc-parallel-25r2"},
}
COUPLING_RECEIVER_RE = re.compile(r"^(coupling|sysc|sc|root|datamodel)", re.IGNORECASE)
FRACTION_NAME_RE = re.compile(r"fraction", re.IGNORECASE)


def _add(
    diagnostics: list[Diagnostic],
    options: LintOptions,
    *,
    code: str,
    severity: Severity,
    message: str,
    file_path: str = "",
    line: int | None = None,
    column: int | None = None,
    explanation: str = "",
    suggested_fix: str = "",
    confidence: Confidence = Confidence.MEDIUM,
    is_heuristic: bool = True,
    source_id: str = "",
) -> None:
    diag = Diagnostic(
        code=code,
        severity=severity,
        message=message,
        line=line,
        column=column,
        product="system-coupling",
        dialect="system-coupling-python",
        detected_version=options.target_version,
        file_path=file_path,
        explanation=explanation,
        suggested_fix=suggested_fix,
        confidence=confidence,
        is_heuristic=is_heuristic,
    )
    if source_id:
        fields = source(source_id)
        diag.source_id = fields["source_id"]
        diag.source_url = fields["source_url"]
        diag.source_title = fields["source_title"]
    diagnostics.append(diag)


def lint(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
    mapper: CoordMapper | None = None,
) -> list[Diagnostic]:
    """Lint System Coupling Python content."""
    del mapper  # SysC scripts are plain Python files; no remapping needed.
    diagnostics: list[Diagnostic] = []

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        _add(
            diagnostics,
            options,
            code="PYTHON_SYNTAX_ERROR",
            severity=Severity.ERROR,
            message=f"Python syntax error: {exc.msg}",
            file_path=file_path,
            line=exc.lineno or 1,
            column=exc.offset or 1,
            explanation="The script must parse as Python before command checks mean anything.",
            suggested_fix="Fix the reported Python syntax error.",
            confidence=Confidence.HIGH,
            is_heuristic=False,
        )
        return diagnostics

    seen_commands: set[str] = set()
    fraction_values: list[tuple[float, int]] = []
    participant_count = 0
    path_literals: list[tuple[str, int, int]] = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            nonlocal participant_count
            func = node.func
            name = getattr(func, "attr", getattr(func, "id", ""))
            receiver = ""
            if isinstance(func, ast.Attribute):
                base = func.value
                while isinstance(base, ast.Attribute):
                    base = base.value
                if isinstance(base, ast.Name):
                    receiver = base.id

            key = str(name).lower()
            if key in SYSC_COMMANDS:
                seen_commands.add(key)
                if key == "addparticipant":
                    participant_count += 1
                for arg in node.args + [kw.value for kw in node.keywords]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        path_literals.append((arg.value, arg.lineno, arg.col_offset + 1))
                for kw in node.keywords:
                    if (
                        kw.arg
                        and FRACTION_NAME_RE.search(kw.arg)
                        and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, (int, float))
                        and not isinstance(kw.value.value, bool)
                    ):
                        fraction_values.append((float(kw.value.value), kw.value.lineno))
            elif (
                isinstance(name, str)
                and name.startswith(("Add", "Set", "Create"))
                and COUPLING_RECEIVER_RE.match(receiver or "")
                and key not in SYSC_COMMANDS
            ):
                _add(
                    diagnostics,
                    options,
                    code="SYSTEM_COUPLING_UNKNOWN_COMMAND",
                    severity=Severity.INFO,
                    message=f"'{name}' is not in the shipped System Coupling command subset.",
                    file_path=file_path,
                    line=node.lineno,
                    column=node.col_offset + 1,
                    explanation=(
                        "The receiver looks like a coupling object but the method name "
                        "is outside the documented catalog shipped with this linter."
                    ),
                    suggested_fix="Verify against the official System Coupling commands reference.",
                    confidence=Confidence.LOW,
                    is_heuristic=True,
                    source_id="ansys-sysc-reference-25r2",
                )
            self.generic_visit(node)

    visitor = Visitor()
    visitor.visit(tree)

    # Attribute-assigned fractions: obj.ParticipantFraction = 0.5 style
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                attr_name = getattr(target, "attr", "")
                if isinstance(attr_name, str) and FRACTION_NAME_RE.search(attr_name):
                    value = node.value
                    if (
                        isinstance(value, ast.Constant)
                        and isinstance(value.value, (int, float))
                        and not isinstance(value.value, bool)
                    ):
                        fraction_values.append((float(value.value), node.lineno))

    # Structurally evident sequence requirements.
    if seen_commands:
        if "addparticipant" not in seen_commands:
            _add(
                diagnostics,
                options,
                code="SYSTEM_COUPLING_MISSING_PARTICIPANT",
                severity=Severity.WARNING,
                message="No AddParticipant() call found.",
                file_path=file_path,
                explanation="A coupling setup without registered participants cannot start.",
                suggested_fix="Call AddParticipant() for every participant solver before Initialize().",
                confidence=Confidence.MEDIUM,
                is_heuristic=True,
                source_id="ansys-sysc-reference-25r2",
            )
        if "solve" not in seen_commands:
            _add(
                diagnostics,
                options,
                code="SYSTEM_COUPLING_MISSING_SOLVE",
                severity=Severity.WARNING,
                message="No Solve() call found.",
                file_path=file_path,
                explanation="Without Solve() the coupling script registers a case but never runs it.",
                suggested_fix="Add Solve() after initialization unless another driver runs it.",
                confidence=Confidence.MEDIUM,
                is_heuristic=True,
                source_id="ansys-sysc-reference-25r2",
            )

    # Allocation-fraction arithmetic on literal values.
    if len(fraction_values) >= 2:
        total = sum(value for value, _line in fraction_values)
        if abs(total - 1.0) > 0.001:
            first_line = min(line for _value, line in fraction_values)
            _add(
                diagnostics,
                options,
                code="SYSTEM_COUPLING_ALLOCATION_INVALID",
                severity=Severity.ERROR,
                message=(
                    f"Participant fractions sum to {total:g}; a valid allocation must total 1.0."
                ),
                file_path=file_path,
                line=first_line,
                explanation=(
                    "Each coupled participant receives part of the whole allocation; "
                    "the literal fractions in this script do not add up to the whole."
                ),
                suggested_fix="Adjust participant fractions so they sum to 1.0 across participants.",
                confidence=Confidence.HIGH,
                is_heuristic=False,
                source_id="ansys-sysc-hpc-parallel-25r2",
            )
    elif len(fraction_values) == 1:
        value, line_no = fraction_values[0]
        if value < 1.0 and participant_count <= 1:
            _add(
                diagnostics,
                options,
                code="SYSTEM_COUPLING_ALLOCATION_INCOMPLETE",
                severity=Severity.INFO,
                message=(
                    f"A single participant fraction of {value:g} leaves "
                    f"{1 - value:g} of the allocation unassigned."
                ),
                file_path=file_path,
                line=line_no,
                explanation="If more participants exist elsewhere their fractions must complete the allocation.",
                suggested_fix="Confirm every participant has its share; fractions should total 1.0.",
                confidence=Confidence.LOW,
                is_heuristic=True,
                source_id="ansys-sysc-hpc-parallel-25r2",
            )

    # Deduplicate identical literal references before scanning.
    unique_literals: list[tuple[str, int, int]] = []
    seen_literal_keys: set[tuple[str, int]] = set()
    for literal, line_no, col_no in path_literals:
        key = (literal, line_no)
        if key not in seen_literal_keys:
            seen_literal_keys.add(key)
            unique_literals.append((literal, line_no, col_no))

    for literal, line_no, col_no in unique_literals:
        for finding in scan_path_literal(
            literal,
            target_os=options.target_os,
            line=line_no,
            column=col_no,
            label="participant path",
        ):
            _add(
                diagnostics,
                options,
                code=finding.code,
                severity=finding.severity,
                message=finding.message,
                file_path=file_path,
                line=line_no,
                column=col_no,
                explanation=finding.explanation,
                suggested_fix=finding.suggested_fix,
                confidence=finding.confidence,
                is_heuristic=finding.is_heuristic,
            )

    return diagnostics


def is_sysc_script(text: str) -> bool:
    """Cheap structural signature used by the detector registry."""
    lowered_names = ("addparticipant(", "addinterface(", "adddatatransfer(", "datamodelroot(")
    lowered = text.lower()
    return any(marker in lowered for marker in lowered_names)
