"""Ansys CCL family linter: CFX-Pre sessions/states, CFD-Post
sessions (.cse) and states (.cst), TurboGrid sessions (.tse) and
states (.tst).

Coverage model:

- *Exact/structural*: CCL object block balance (``NAME :`` ... ``END``),
  stray END detection, CEL parenthesis balance inside parameter values,
  Power Syntax (``!``) line isolation, ``>quit`` termination rules for
  batch session files.
- *Heuristic*: absolute-path and Windows-path portability of referenced
  result/mesh/state files, shell execution inside Power Syntax,
  GUI-flavoured actions in unattended runs.

Object-level validation across products is deliberately NOT attempted:
TurboGrid does not accept every CFD-Post CCL object and no authoritative
cross-product object catalog ships with this plugin (see docs/coverage).
"""

from __future__ import annotations

import re

from ..model import Confidence, CoordMapper, Diagnostic, LintOptions, Severity
from ..rules_common import scan_path_literal
from ..sources import resolve as source
from ..textlines import LineIndex

HEADER_RE = re.compile(r"^\s*([^=><#!\s][^:=]*?)\s*:(?!/)\s*(.*)$")
ASSIGN_RE = re.compile(r"^(\s*)([A-Za-z][\w .\-]*?)\s*=\s*(.*)$")
KNOWN_FILE_SUFFIXES = (
    ".res",
    ".msh",
    ".ccl",
    ".cse",
    ".cst",
    ".pre",
    ".csv",
    ".out",
    ".cgns",
    ".gtm",
)
GUI_ACTION_PREFIXES = (">show", ">view", ">plot", ">image", ">render")
POWER_SYNTAX_SYSTEM_RE = re.compile(r"`[^`]+`|system\s*\(")


def _add(
    diagnostics: list[Diagnostic],
    lines: LineIndex,
    options: LintOptions,
    *,
    code: str,
    severity: Severity,
    message: str,
    offset_or_none: int | None,
    file_path: str,
    product: str,
    dialect: str,
    explanation: str = "",
    suggested_fix: str = "",
    confidence: Confidence = Confidence.MEDIUM,
    is_heuristic: bool = True,
    source_id: str = "",
    mapper: CoordMapper | None = None,
) -> None:
    line = column = None
    if offset_or_none is not None:
        line, column = lines.line_col(offset_or_none)
        if mapper is not None:
            line, column = mapper.map_line_col(line, column)
            if mapper.note:
                message = f"{message} {mapper.note}".strip()
    diag = Diagnostic(
        code=code,
        severity=severity,
        message=message,
        line=line,
        column=column,
        product=product,
        dialect=dialect,
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


def _paren_delta(expression: str) -> int:
    depth = 0
    in_quote = False
    quote = ""
    for ch in expression:
        if in_quote:
            if ch == quote:
                in_quote = False
            continue
        if ch in "\"'":
            in_quote = True
            quote = ch
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
    return depth


def lint(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
    product: str = "cfx",
    kind: str = "state",
    mapper: CoordMapper | None = None,
) -> list[Diagnostic]:
    """Lint CCL content.

    ``product``: cfx | cfd-post | turbo-grid
    ``kind``: session | state
    """
    dialect = {
        ("cfx", "session"): "cfx-pre-session",
        ("cfx", "state"): "ccl",
        ("cfd-post", "session"): "cfd-post-session",
        ("cfd-post", "state"): "cfd-post-state",
        ("turbo-grid", "session"): "turbo-grid-session",
        ("turbo-grid", "state"): "turbo-grid-state",
    }.get((product, kind), "ccl")

    diagnostics: list[Diagnostic] = []
    lines = LineIndex(text)
    source_id_default = (
        "ansys-turbo-ccl-25r2"
        if product == "turbo-grid"
        else ("ansys-cfdpost-ccl-25r2" if product == "cfd-post" else "ansys-cfx-ccl-25r2")
    )

    open_blocks: list[tuple[str, int]] = []  # (name, line number)
    action_lines: list[tuple[int, str]] = []
    referenced_files: list[tuple[str, int]] = []
    power_lines: list[tuple[int, str]] = []
    saw_quit = False

    for index in range(1, lines.line_count + 1):
        raw = lines.line_text(index)
        stripped = raw.strip()
        if not stripped:
            continue
        offset = lines.offset(index, len(raw) - len(stripped) + 1)

        # Power Syntax lines execute Perl statements verbatim.
        if stripped.startswith("!"):
            power_lines.append((index, stripped))
            continue

        # Session action commands begin with '>'.
        if stripped.startswith(">"):
            action = stripped.rstrip()
            action_lines.append((index, action))
            if action.lower().rstrip(";").strip() == ">quit":
                saw_quit = True
            lowered_action = action.lower()
            if any(lowered_action.startswith(prefix) for prefix in GUI_ACTION_PREFIXES):
                if options.exec_mode.value != "interactive":
                    _add(
                        diagnostics,
                        lines,
                        options,
                        code="GUI_DEPENDENT_ACTION",
                        severity=Severity.WARNING,
                        message=f"Action '{action.split()[0]}' typically needs the interactive viewer.",
                        offset_or_none=offset,
                        file_path=file_path,
                        product=product,
                        dialect=dialect,
                        explanation=(
                            "Viewer/plotting actions depend on an interactive graphics "
                            "session; batch runs usually cannot satisfy them."
                        ),
                        suggested_fix="Remove viewer actions from batch session files.",
                        confidence=Confidence.LOW,
                        is_heuristic=True,
                    )
            # harvest path-like arguments of actions such as '>load ...'
            parts = action.split()
            if len(parts) >= 2:
                candidate = parts[-1].strip("'\";")
                if candidate.lower().endswith(KNOWN_FILE_SUFFIXES):
                    referenced_files.append((candidate, index))
            continue

        # Comments start with '#'.
        if stripped.startswith("#"):
            continue

        # Object terminator.
        if re.fullmatch(r"[Ee][Nn][Dd]\s*;?", stripped):
            if not open_blocks:
                _add(
                    diagnostics,
                    lines,
                    options,
                    code="CCL_UNEXPECTED_END",
                    severity=Severity.ERROR,
                    message="'END' without a matching object header.",
                    offset_or_none=offset,
                    file_path=file_path,
                    product=product,
                    dialect=dialect,
                    explanation="Every END terminates the most recent unclosed CCL object block.",
                    suggested_fix="Remove the stray END or add the missing object header above it.",
                    confidence=Confidence.HIGH,
                    is_heuristic=False,
                    source_id=source_id_default,
                )
            else:
                open_blocks.pop()
            continue

        # Parameter assignment (CEL value).
        assign_match = ASSIGN_RE.match(stripped)
        if assign_match and ":" not in stripped.split("=")[0]:
            value = assign_match.group(3)
            delta = _paren_delta(value)
            if delta != 0:
                _add(
                    diagnostics,
                    lines,
                    options,
                    code="CEL_UNBALANCED_PARENS",
                    severity=Severity.ERROR,
                    message="CEL expression parentheses do not balance in this parameter value.",
                    offset_or_none=offset,
                    file_path=file_path,
                    product=product,
                    dialect=dialect,
                    explanation="Unbalanced parentheses change how the CEL expression evaluates.",
                    suggested_fix="Balance '(' and ')' inside the parameter value.",
                    confidence=Confidence.HIGH,
                    is_heuristic=False,
                )
            for token in re.findall(r"[^\s,]+", value):
                token_clean = token.strip("'\"")
                if token_clean.lower().endswith(KNOWN_FILE_SUFFIXES):
                    referenced_files.append((token_clean, index))
            continue

        # Object header 'NAME :' / 'NAME : TYPE:'.
        header_match = HEADER_RE.match(stripped)
        if header_match:
            name = header_match.group(1).strip()
            remainder = header_match.group(2).strip()
            if remainder.endswith(":"):
                remainder = remainder[:-1].strip()
            if name:
                open_blocks.append((name, index))
                continue

        # Unrecognised line inside/outside blocks: leave alone - CCL dialects
        # vary legitimately between products; only structural issues are exact.

    # ---- End-of-file structural checks -------------------------------------
    for name, opening_line in open_blocks:
        _add(
            diagnostics,
            lines,
            options,
            code="CCL_UNTERMINATED_OBJECT",
            severity=Severity.ERROR,
            message=f"CCL object '{name}' opened here is never terminated by 'END'.",
            offset_or_none=lines.offset(opening_line, 1),
            file_path=file_path,
            product=product,
            dialect=dialect,
            explanation="Unterminated CCL objects make the rest of the file fail to parse.",
            suggested_fix=f"Add an 'END' line closing '{name}'.",
            confidence=Confidence.HIGH,
            is_heuristic=False,
            source_id=source_id_default,
        )

    if product == "turbo-grid" and kind == "session":
        has_actions = bool(action_lines)
        if has_actions and not saw_quit and text.strip():
            last_line = max(line for line, _action in action_lines)
            _add(
                diagnostics,
                lines,
                options,
                code="TURBOGRID_BATCH_QUIT_MISSING",
                severity=Severity.ERROR,
                message="Batch TurboGrid sessions must end with the '>quit' action.",
                offset_or_none=lines.offset(last_line, 1),
                file_path=file_path,
                product=product,
                dialect=dialect,
                explanation=(
                    "Without a final '>quit' the cfxtg -batch run waits at the "
                    "command prompt and holds the allocation until it times out."
                ),
                suggested_fix="Append '>quit' as the final action line.",
                confidence=Confidence.HIGH,
                is_heuristic=False,
                source_id="ansys-turbo-batch-25r2",
            )
    elif product == "cfd-post" and kind == "session":
        has_actions = bool(action_lines)
        if has_actions and not saw_quit and options.exec_mode.value != "interactive":
            _add(
                diagnostics,
                lines,
                options,
                code="SESSION_QUIT_MISSING",
                severity=Severity.INFO,
                message="Session file performs actions but never quits.",
                offset_or_none=None,
                file_path=file_path,
                product=product,
                dialect=dialect,
                explanation="Batch CFD-Post sessions normally terminate with '>quit'.",
                suggested_fix="Append '>quit' unless the driver script closes CFD-Post itself.",
                confidence=Confidence.MEDIUM,
                is_heuristic=True,
            )

    # ---- Power Syntax --------------------------------------------------------
    for index, statement in power_lines:
        body = statement[1:]
        if POWER_SYNTAX_SYSTEM_RE.search(body):
            _add(
                diagnostics,
                lines,
                options,
                code="SECURITY_EXTERNAL_PROCESS",
                severity=Severity.WARNING,
                message="Power Syntax line executes an external command via Perl.",
                offset_or_none=lines.offset(index, 1),
                file_path=file_path,
                product=product,
                dialect=dialect,
                explanation="Perl backticks/system calls hand commands to the OS shell.",
                suggested_fix="Avoid shell-outs in batch session files.",
                confidence=Confidence.HIGH,
                is_heuristic=False,
            )

    # ---- Portability of referenced files --------------------------------------
    for name, line_no in referenced_files:
        for finding in scan_path_literal(
            name,
            target_os=options.target_os,
            line=line_no,
            column=1,
            label="referenced file",
        ):
            _add(
                diagnostics,
                lines,
                options,
                code=finding.code,
                severity=finding.severity,
                message=finding.message,
                offset_or_none=lines.offset(line_no, 1),
                file_path=file_path,
                product=product,
                dialect=dialect,
                explanation=finding.explanation,
                suggested_fix=finding.suggested_fix,
                confidence=finding.confidence,
                is_heuristic=finding.is_heuristic,
            )

    return diagnostics
