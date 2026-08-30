"""ICEM CFD replay script linter (.rpl - a Tcl/Tk variation).

Coverage model:

- *Exact/structural*: Tcl command-boundary scanning (braces, brackets,
  quotes, backslash continuation, comments), unbalanced-brace detection.
- *Heuristic*: recognition of ``ic_*`` commands against a documented
  subset, warnings for undocumented internal ``ic_*`` names, external
  process execution via ``exec``/pipes, GUI-dependent replay commands in
  batch mode.

Replay files are recorded by ICEM itself; the official documentation
states that not all internal ``ic_*`` commands are documented. The linter
therefore never claims an ``ic_*`` name is *invalid* - only that it is
undocumented in the shipped subset.
"""

from __future__ import annotations

from ..model import Confidence, CoordMapper, Diagnostic, LintOptions, Severity
from ..rules_common import scan_path_literal
from ..sources import resolve as source
from ..textlines import LineIndex

KNOWN_IC_COMMANDS = frozenset(
    {
        "ic_point",
        "ic_line",
        "ic_curve",
        "ic_surface",
        "ic_part",
        "ic_undo_begin",
        "ic_undo_end",
    }
)
COMMON_TCL_COMMANDS = frozenset(
    {
        "set",
        "unset",
        "puts",
        "expr",
        "file",
        "source",
        "glob",
        "cd",
        "pwd",
        "exec",
        "open",
        "close",
        "flush",
        "read",
        "gets",
        "after",
        "catch",
        "foreach",
        "while",
        "if",
        "else",
        "elseif",
        "proc",
        "return",
        "format",
        "string",
        "list",
        "lindex",
        "llength",
        "lsort",
        "split",
        "join",
        "incr",
        "global",
        "variable",
        "array",
        "info",
        "error",
        "tk_messageBox",
        "wm",
        "pack",
        "grid",
        "frame",
        "button",
        "label",
        "entry",
        "canvas",
        "bind",
        "focus",
        "update",
        "destroy",
        "console",
    }
)
GUI_HINT_COMMANDS = frozenset({"wm", "pack", "grid", "canvas", "bind", "focus", "destroy", "tk_messageBox"})


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
        product="icem-cfd",
        dialect="icem-replay-tcl",
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


def _scan_commands(text: str) -> tuple[list[tuple[str, int]], list[tuple[str, str, int]]]:
    """Split Tcl text into top-level command words.

    Returns:
        commands: (first_word, line) per command
        issues: (code, message, offset) structural problems
    """
    commands: list[tuple[str, int]] = []
    issues: list[tuple[str, str, int]] = []
    i = 0
    n = len(text)
    brace_stack: list[tuple[str, int]] = []  # (char, offset)
    bracket_stack: list[int] = []

    def current_line(offset: int) -> int:
        return text.count("\n", 0, offset) + 1

    at_command_start = True

    while i < n:
        ch = text[i]

        # Comments are only comments at command position.
        if ch == "#" and at_command_start:
            nl = text.find("\n", i)
            i = n if nl == -1 else nl + 1
            at_command_start = True
            continue

        if ch == "\n":
            # continuation?
            j = i - 1
            cont = False
            while j >= 0 and text[j] in " \t\r":
                j -= 1
            if j >= 0 and text[j] == "\\":
                cont = True
            if not brace_stack and not bracket_stack and not cont:
                at_command_start = True
            i += 1
            continue

        if ch in " \t\r;":
            if ch == ";":
                at_command_start = True
            i += 1
            continue

        if ch == "{":
            brace_stack.append(("{", i))
            i += 1
            continue
        if ch == "}":
            if not brace_stack or brace_stack[-1][0] != "{":
                issues.append(("TCL_UNBALANCED_BRACE", "'}' closes nothing or closes a '\"'.", i))
            else:
                brace_stack.pop()
            i += 1
            continue

        if ch == "[":
            bracket_stack.append(i)
            i += 1
            continue
        if ch == "]":
            if not bracket_stack:
                issues.append(("TCL_UNBALANCED_BRACKET", "']' without a matching '['.", i))
            else:
                bracket_stack.pop()
            i += 1
            continue

        if ch == '"':
            j = i + 1
            closed = False
            while j < n:
                cj = text[j]
                if cj == "\\":
                    j += 2
                    continue
                if cj == '"':
                    closed = True
                    break
                if cj == "\n" and not brace_stack and not bracket_stack:
                    break
                j += 1
            if not closed:
                issues.append(("TCL_UNCLOSED_QUOTE", "Double-quoted word is never closed.", i))
                i = j + 1
                continue
            i = j + 1
            continue

        # bare word
        start = i
        depth_brace = len(brace_stack)
        depth_bracket = len(bracket_stack)
        while i < n:
            c = text[i]
            if c in " \t\r\n;":
                if len(brace_stack) > depth_brace or len(bracket_stack) > depth_bracket:
                    i += 1
                    continue
                break
            if c == "\\":
                i += 2
                continue
            if c in "{[\"]":
                break
            i += 1
        word = text[start:i]
        if at_command_start and word:
            commands.append((word, current_line(start)))
            at_command_start = False
        elif word and word.startswith("$"):
            pass
        continue

    for opener_char, offset in brace_stack:
        issues.append(("TCL_UNCLOSED_BRACE", f"'{opener_char}' opened here is never closed.", offset))
    for offset in bracket_stack:
        issues.append(("TCL_UNCLOSED_BRACKET", "'[' opened here is never closed.", offset))

    return commands, issues


def lint(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
    mapper: CoordMapper | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    lines = LineIndex(text)

    commands, issues = _scan_commands(text)

    for code, message, offset in issues:
        severity = Severity.ERROR
        _add(
            diagnostics,
            lines,
            options,
            code=code,
            severity=severity,
            message=message,
            offset_or_none=offset,
            file_path=file_path,
            explanation="Unbalanced Tcl structure changes how every later replay line is parsed.",
            suggested_fix="Fix braces/brackets/quotes before trusting further results.",
            confidence=Confidence.HIGH,
            is_heuristic=False,
            mapper=mapper,
        )

    undo_open: int | None = None
    path_args: list[tuple[str, int]] = []
    unattended = options.exec_mode.value != "interactive"

    for word, line_no in commands:
        lowered = word.lower()

        if lowered.startswith("ic_"):
            if lowered not in KNOWN_IC_COMMANDS:
                _add(
                    diagnostics,
                    lines,
                    options,
                    code="ICEM_UNDOCUMENTED_COMMAND",
                    severity=Severity.WARNING,
                    message=f"'{word}' is an internal ICEM command outside the shipped documented subset.",
                    offset_or_none=lines.offset(line_no, 1),
                    file_path=file_path,
                    explanation=(
                        "Ansys documents that replay scripts may call undocumented "
                        "internal commands. They often work but can change without "
                        "notice between releases."
                    ),
                    suggested_fix="Verify this command still exists in your installed ICEM release.",
                    confidence=Confidence.LOW,
                    is_heuristic=True,
                    source_id="ansys-icem-replay-25r2",
                    mapper=mapper,
                )
            elif lowered == "ic_undo_begin":
                undo_open = line_no
            elif lowered == "ic_undo_end":
                undo_open = None
            continue

        if lowered == "exec":
            _add(
                diagnostics,
                lines,
                options,
                code="SECURITY_EXTERNAL_PROCESS",
                severity=Severity.WARNING,
                message="Tcl 'exec' launches an external program.",
                offset_or_none=lines.offset(line_no, 1),
                file_path=file_path,
                explanation="External execution depends on the node environment and may block the batch job.",
                suggested_fix="Remove exec calls from replay scripts run on HPC nodes.",
                confidence=Confidence.HIGH,
                is_heuristic=False,
                mapper=mapper,
            )
            continue

        if lowered in ("open", "source", "cd", "glob"):
            # harvest following word-ish args on same logical line for portability
            line_text = lines.line_text(line_no)
            for token in line_text.split()[1:]:
                cleaned = token.strip("{}\"")
                if "/" in cleaned or "\\" in cleaned or cleaned.startswith("~"):
                    path_args.append((cleaned, line_no))
                    break

        if unattended and lowered in GUI_HINT_COMMANDS:
            _add(
                diagnostics,
                lines,
                options,
                code="GUI_DEPENDENT_REPLAY_COMMAND",
                severity=Severity.INFO,
                message=f"'{word}' manipulates Tk GUI state and has no effect headless.",
                offset_or_none=lines.offset(line_no, 1),
                file_path=file_path,
                explanation="Recorded replays sometimes include window/GUI calls that do nothing in batch.",
                suggested_fix="Remove GUI-only commands from batch replay scripts.",
                confidence=Confidence.LOW,
                is_heuristic=True,
                mapper=mapper,
            )

        if lowered not in COMMON_TCL_COMMANDS and not lowered.startswith("ic_") and not lowered.startswith("."):
            _add(
                diagnostics,
                lines,
                options,
                code="TCL_UNKNOWN_COMMAND",
                severity=Severity.INFO,
                message=f"'{word}' is not a standard Tcl command in the shipped subset.",
                offset_or_none=lines.offset(line_no, 1),
                file_path=file_path,
                explanation="Could be an application-defined proc from the ICEM session; verify manually.",
                confidence=Confidence.LOW,
                is_heuristic=True,
                mapper=mapper,
            )

    if undo_open is not None:
        _add(
            diagnostics,
            lines,
            options,
            code="ICEM_UNDO_SECTION_OPEN",
            severity=Severity.WARNING,
            message="'ic_undo_begin' without a matching 'ic_undo_end'.",
            offset_or_none=lines.offset(undo_open, 1),
            file_path=file_path,
            explanation=(
                "Undo sections record raw interactive steps; replaying an unclosed "
                "section can leave the geometry history inconsistent."
            ),
            suggested_fix="Close the section with ic_undo_end or trim it manually.",
            confidence=Confidence.MEDIUM,
            is_heuristic=False,
            mapper=mapper,
        )

    for name, line_no in path_args:
        for finding in scan_path_literal(
            name,
            target_os=options.target_os,
            line=line_no,
            column=1,
            label="path argument",
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
                explanation=finding.explanation,
                suggested_fix=finding.suggested_fix,
                confidence=finding.confidence,
                is_heuristic=finding.is_heuristic,
                mapper=mapper,
            )

    return diagnostics


