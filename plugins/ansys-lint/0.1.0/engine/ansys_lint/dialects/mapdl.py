"""Mechanical APDL linter (batch input, .dat/.inp/.mac/.log replay).

Coverage model:

- *Exact/structural*: case-insensitive command tokenisation, processor
  tracking for /PREP7 //SOLUTION //POST1 //POST26 + FINISH, block pairing
  (*DO/*ENDDO, *IF/*ENDIF, *CREATE/*END, *PYTHON/*ENDPY), embedded Python
  syntax inside *PYTHON blocks.
- *Catalog-backed*: command names and conservative processor-context hints
  against the shipped catalog (partial; see data/mapdl_commands.json).
- *Heuristic*: missing solve/output suggestions, graphics-in-batch notes,
  portability of referenced paths, security warnings for /SYS and ~e.

Strictness mode: in ``strict`` mode unknown commands become warnings instead
of informational notes.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ..model import Confidence, Diagnostic, LintOptions, Severity
from ..rules_common import case_insensitive_duplicates, scan_path_literal
from ..sources import resolve as source
from ..textlines import LineIndex

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

TOKEN_RE = re.compile(r"^[/~*A-Za-z][\w/\-.]*")
LABEL_RE = re.compile(r"^:[A-Za-z_][\w\-]*")
PATH_COMMANDS = ("/INPUT", "CDREAD", "PARRES", "*USE")
OUTPUT_COMMANDS = ("SAVE", "CDWRITE", "*CFOPEN", "*MWRITE", "PARSAV")
PROCESSOR_PRETTY = {
    "prep7": "/PREP7",
    "solution": "/SOLUTION",
    "post1": "/POST1",
    "post26": "/POST26",
}


@lru_cache(maxsize=2)
def load_catalog(data_dir: str | None = None) -> dict:
    path = Path(data_dir) / "mapdl_commands.json" if data_dir else DATA_DIR / "mapdl_commands.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@dataclass
class MapdlContext:
    options: LintOptions
    file_path: str
    diagnostics: list[Diagnostic] = field(default_factory=list)
    processor: str | None = None
    saw_model_or_load: bool = False
    saw_solve: bool = False
    saw_output: bool = False


def _add(
    ctx: MapdlContext,
    lines: LineIndex,
    *,
    code: str,
    severity: Severity,
    message: str,
    line: int | None,
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
        product="mapdl",
        dialect="mapdl",
        detected_version=ctx.options.target_version,
        file_path=ctx.file_path,
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
    ctx.diagnostics.append(diag)


def _split_statements(line: str) -> list[str]:
    """Split a physical line on the APDL '$' statement separator."""
    parts: list[str] = []
    buf: list[str] = []
    in_quote = False
    quote = ""
    for ch in line:
        if in_quote:
            buf.append(ch)
            if ch == quote:
                in_quote = False
            continue
        if ch in "'\"":
            in_quote = True
            quote = ch
            buf.append(ch)
            continue
        if ch == "$":
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    parts.append("".join(buf))
    return parts


def _strip_comment(statement: str) -> str:
    """Remove trailing '! comment' outside quotes."""
    out: list[str] = []
    in_quote = False
    quote = ""
    for ch in statement:
        if in_quote:
            out.append(ch)
            if ch == quote:
                in_quote = False
            continue
        if ch in "'\"":
            in_quote = True
            quote = ch
            out.append(ch)
            continue
        if ch == "!":
            break
        out.append(ch)
    return "".join(out).rstrip()


def _check_python_block(
    ctx: MapdlContext,
    lines: LineIndex,
    code_lines: list[tuple[int, str]],
) -> None:
    body = "\n".join(text for _line, text in code_lines)
    if not body.strip():
        return
    try:
        ast.parse(body)
    except SyntaxError as exc:
        first_line = code_lines[0][0]
        inner_line = first_line + (exc.lineno or 1) - 1
        _add(
            ctx,
            lines,
            code="PYTHON_SYNTAX_ERROR",
            severity=Severity.ERROR,
            message=f"Embedded Python block has a syntax error: {exc.msg}",
            line=inner_line,
            column=(exc.offset or 1),
            explanation="Content between *PYTHON and *ENDPY must parse as Python.",
            suggested_fix="Fix the Python syntax inside the embedded block.",
            confidence=Confidence.HIGH,
            is_heuristic=False,
        )


def lint(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
) -> list[Diagnostic]:
    catalog = load_catalog()
    commands: dict[str, dict] = catalog["commands"]
    block_pairs: dict[str, str] = catalog["block_pairs"]
    security_cmds: dict[str, str] = catalog["security_commands"]
    graphics_cmds: set[str] = set(catalog["graphics_commands"])
    closers_to_openers = {closer: opener for opener, closer in block_pairs.items()}

    ctx = MapdlContext(options=options, file_path=file_path)
    lines = LineIndex(text)
    open_blocks: list[tuple[str, int]] = []
    referenced_files: list[tuple[str, int]] = []
    strict = options.strictness.value == "strict"
    unattended = options.exec_mode.value != "interactive"

    python_active = False
    python_code_lines: list[tuple[int, str]] = []

    def finish_python_block() -> None:
        nonlocal python_active
        python_active = False
        _check_python_block(ctx, lines, python_code_lines)
        python_code_lines.clear()

    for index in range(1, lines.line_count + 1):
        raw = lines.line_text(index)
        stripped_raw = raw.strip()
        if not stripped_raw:
            continue

        # Inside an embedded Python block, collect verbatim until *ENDPY.
        if python_active:
            if stripped_raw.upper().startswith("*ENDPY"):
                finish_python_block()
            else:
                python_code_lines.append((index, raw))
            continue

        for statement in _split_statements(raw):
            cleaned = _strip_comment(statement).strip()
            if not cleaned:
                continue
            column = len(statement) - len(statement.lstrip()) + 1

            if LABEL_RE.match(cleaned):
                continue  # branch target label

            token_match = TOKEN_RE.match(cleaned)
            if token_match is None:
                continue
            token = token_match.group(0)
            cmd = token.upper()
            rest = cleaned[len(token) :].strip()
            entry = commands.get(cmd)
            if entry is None and not cmd.startswith("/"):
                # Slash commands may legally drop the leading slash
                # (e.g. 'PREP7' instead of '/PREP7').
                slashed = "/" + cmd
                if slashed in commands:
                    entry = commands[slashed]
                    if (entry or {}).get("kind") == "processor-enter":
                        cmd = slashed

            # --- Security-sensitive commands ---------------------------------
            if cmd in security_cmds or cmd.startswith("~E"):
                reason = security_cmds.get(cmd, "Executes an external binary.")
                _add(
                    ctx,
                    lines,
                    code="SECURITY_EXTERNAL_PROCESS",
                    severity=Severity.WARNING,
                    message=f"{cmd} executes an external program ({reason.rstrip('.')}).",
                    line=index,
                    column=column,
                    explanation=(
                        "External execution depends on the compute node environment "
                        "and can touch files outside the job directory."
                    ),
                    suggested_fix="Avoid OS/exec calls in batch APDL inputs.",
                    confidence=Confidence.HIGH,
                    is_heuristic=False,
                    source_id="ansys-mapdl-command-reference-25r2",
                )

            # --- Embedded Python blocks ---------------------------------------
            if cmd == "*PYTHON":
                python_active = True
                python_code_lines.clear()
                continue
            if cmd == "*ENDPY":
                finish_python_block()
                continue

            # --- Processor transitions -----------------------------------------
            kind = (entry or {}).get("kind")
            if kind == "processor-enter":
                ctx.processor = str(entry.get("target"))
            elif kind == "processor-exit":
                ctx.processor = None

            # --- Block structure -------------------------------------------------
            if entry is not None and cmd in block_pairs:
                open_blocks.append((cmd, index))
            elif cmd in closers_to_openers:
                expected_opener = closers_to_openers[cmd]
                if not open_blocks or open_blocks[-1][0] != expected_opener:
                    _add(
                        ctx,
                        lines,
                        code=f"MAPDL_UNBALANCED_{expected_opener.lstrip('*')}",
                        severity=Severity.ERROR,
                        message=f"'{cmd}' without a matching '{expected_opener}'.",
                        line=index,
                        column=column,
                        explanation="Control blocks must open before they close.",
                        suggested_fix=f"Remove '{cmd}' or add the matching '{expected_opener}'.",
                        confidence=Confidence.HIGH,
                        is_heuristic=False,
                    )
                else:
                    open_blocks.pop()

            # --- Unknown commands -----------------------------------------------
            if entry is None:
                severity = Severity.WARNING if strict else Severity.INFO
                _add(
                    ctx,
                    lines,
                    code="MAPDL_UNKNOWN_COMMAND",
                    severity=severity,
                    message=f"'{cmd}' is not in the shipped MAPDL catalog.",
                    line=index,
                    column=column,
                    explanation=(
                        "APDL is case-insensitive; this name was upper-cased before "
                        "lookup. The shipped catalog covers common commands only, so "
                        "the command may still be valid - verify it against the "
                        "official Command Reference for your installed release."
                    ),
                    suggested_fix="Check spelling and availability in the official MAPDL Command Reference.",
                    confidence=Confidence.LOW,
                    is_heuristic=True,
                    source_id=str(catalog["source_id"]),
                )

            # --- Processor context hints --------------------------------------------
            allowed = (entry or {}).get("processors") or []
            if entry is not None and allowed and ctx.processor is not None and ctx.processor not in allowed:
                _add(
                    ctx,
                    lines,
                    code="MAPDL_PROCESSOR_CONTEXT",
                    severity=Severity.WARNING,
                    message=(
                        f"'{cmd}' is documented for "
                        f"{', '.join(PROCESSOR_PRETTY.get(p, p) for p in allowed)} but "
                        f"the current processor is {PROCESSOR_PRETTY.get(ctx.processor, ctx.processor)}."
                    ),
                    line=index,
                    column=column,
                    explanation=(
                        "Processor hints are only populated where official "
                        "documentation clearly restricts usage."
                    ),
                    suggested_fix="Enter the documented processor before using this command.",
                    confidence=Confidence.MEDIUM,
                    is_heuristic=False,
                    source_id=str(catalog["source_id"]),
                )

            # --- Workflow bookkeeping -----------------------------------------------
            if entry is not None and "prep7" in allowed:
                ctx.saw_model_or_load = True
            if cmd in ("SOLVE", "LSSOLVE"):
                ctx.saw_solve = True
            if any(cmd.startswith(w) for w in OUTPUT_COMMANDS):
                ctx.saw_output = True

            # --- Graphics in batch -----------------------------------------------------
            if unattended and cmd in graphics_cmds:
                _add(
                    ctx,
                    lines,
                    code="MAPDL_GRAPHICS_IN_BATCH",
                    severity=Severity.INFO,
                    message=f"'{cmd}' controls interactive display output.",
                    line=index,
                    column=column,
                    explanation=(
                        "In batch mode displays are usually redirected; without /SHOW "
                        "routing these commands have little effect."
                    ),
                    suggested_fix="Add e.g. '/SHOW,,PNG' early in batch inputs when images are wanted.",
                    confidence=Confidence.LOW,
                    is_heuristic=True,
                    source_id="ansys-mapdl-batch-mode-25r2",
                )

            # --- Referenced paths --------------------------------------------------------
            if cmd in PATH_COMMANDS and rest:
                arg = rest.split(",")[0].strip("'\" ")
                if arg:
                    referenced_files.append((arg, index))
                    for finding in scan_path_literal(
                        arg,
                        target_os=options.target_os,
                        line=index,
                        column=column,
                        label=f"{cmd} argument",
                    ):
                        _add(
                            ctx,
                            lines,
                            code=finding.code,
                            severity=finding.severity,
                            message=finding.message,
                            line=index,
                            column=column,
                            explanation=finding.explanation,
                            suggested_fix=finding.suggested_fix,
                            confidence=finding.confidence,
                            is_heuristic=finding.is_heuristic,
                        )

    # ---- End-of-file structural checks ----------------------------------------
    if python_active:
        _check_python_block(ctx, lines, python_code_lines)

    for opener, opening_line in open_blocks:
        closer = block_pairs[opener]
        _add(
            ctx,
            lines,
            code=f"MAPDL_UNBALANCED_{opener.lstrip('*')}",
            severity=Severity.ERROR,
            message=f"'{opener}' opened here is never closed by '{closer}'.",
            line=opening_line,
            explanation="Unbalanced control blocks change which statements execute.",
            suggested_fix=f"Add the matching '{closer}'.",
            confidence=Confidence.HIGH,
            is_heuristic=False,
        )

    if ctx.saw_model_or_load and not ctx.saw_solve:
        _add(
            ctx,
            lines,
            code="MAPDL_NO_SOLVE",
            severity=Severity.INFO,
            message="Model/loading commands exist but no SOLVE/LSSOLVE follows.",
            line=None,
            explanation="Batch inputs that build or load a model usually end with a solution step.",
            suggested_fix="Add SOLVE (inside /SOLUTION) unless this file is intentionally partial.",
            confidence=Confidence.LOW,
            is_heuristic=True,
        )
    if ctx.saw_solve and not ctx.saw_output:
        _add(
            ctx,
            lines,
            code="MAPDL_NO_OUTPUT",
            severity=Severity.INFO,
            message="A solve happens but no SAVE/CDWRITE/*CFOPEN output follows.",
            line=None,
            explanation="Artifacts beyond the standard results file need explicit output commands.",
            suggested_fix="Consider SAVE or CDWRITE after solving if extra artifacts are needed.",
            confidence=Confidence.LOW,
            is_heuristic=True,
        )

    for _first_name, second_name, _first_line, second_line in case_insensitive_duplicates(referenced_files):
        _add(
            ctx,
            lines,
            code="PORTABILITY_CASE_MISMATCH",
            severity=Severity.WARNING,
            message=f"References differ only by letter case: '{_first_name}' vs '{second_name}'.",
            line=second_line,
            explanation="Linux filesystems are case-sensitive; one of the two references likely points nowhere.",
            suggested_fix="Make file name casing consistent.",
            confidence=Confidence.MEDIUM,
            is_heuristic=False,
        )

    return ctx.diagnostics
