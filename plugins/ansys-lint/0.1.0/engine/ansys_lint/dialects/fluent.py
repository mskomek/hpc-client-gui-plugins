"""Ansys Fluent journal / TUI / Scheme linter.

Coverage model (documented honestly):

- *Exact/structural*: set-tui-version handling, shell escapes, Scheme paren
  balance, output-after-solve structure, bare ``/exit`` prompt risk.
- *Catalog-backed*: known TUI command availability for the selected version
  pack (partial catalog; see data/fluent_tui.json).
- *Heuristic*: unknown-command notes, GUI-prefix warnings in batch mode,
  overwrite handling and path portability recommendations.

The parser never assumes a menu exists merely because it existed in another
release: availability comes from the selected version pack only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..model import (
    Confidence,
    CoordMapper,
    Diagnostic,
    LintOptions,
    Severity,
)
from ..rules_common import case_insensitive_duplicates, scan_path_literal
from ..sources import resolve as source
from ..textlines import LineIndex

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

TUI_TOKEN_RE = re.compile(r"[/A-Za-z][\w/\-.]*")
SCHEME_COMMENT_RE = re.compile(r";")
SET_TUI_ARG_RE = re.compile(
    r"^(?P<major>\d{2})(?:[ .]?R?(?P<rev>\d))?$|^(?P<year>20\d{2})\s*[Rr](?P<rrev>\d)$"
)

WRITE_COMMANDS = (
    "/file/write-case",
    "/file/write-data",
    "/file/write-case-data",
    "/file/write-mesh",
)
EXPORT_PREFIX = "/file/export/"
SOLVE_COMMANDS = ("/solve/iterate", "/solve/dual-time-iterate")
READ_COMMANDS = (
    "/file/read-case",
    "/file/read-data",
    "/file/read-case-data",
    "/file/read-mesh",
)


@dataclass
class FluentContext:
    options: LintOptions
    version: str
    version_index: int
    supported: tuple[str, ...]
    file_path: str
    mapper: CoordMapper | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)


@lru_cache(maxsize=2)
def load_version_pack(data_dir: str | None = None) -> dict[str, Any]:
    path = Path(data_dir) / "fluent_versions.json" if data_dir else DATA_DIR / "fluent_versions.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=2)
def load_tui_catalog(data_dir: str | None = None) -> dict[str, Any]:
    path = Path(data_dir) / "fluent_tui.json" if data_dir else DATA_DIR / "fluent_tui.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def supported_versions() -> tuple[str, ...]:
    return tuple(load_version_pack()["order"])


def default_version() -> str:
    return str(load_version_pack()["default_version"])


def normalize_set_tui_value(raw: str) -> str | None:
    """Map accepted spellings onto a pack version id ('25.2' style).

    Journals commonly quote the argument: /file/set-tui-version "25.2"
    """
    value = raw.strip().strip("\"'").lower()
    pack = load_version_pack()
    order: list[str] = list(pack["order"])
    if value in order:
        return value
    match = SET_TUI_ARG_RE.match(value.replace("-", " ").strip())
    if not match:
        return None
    if match.group("major"):
        candidate = f"{match.group('major')}.{match.group('rev') or '0'}"
        return candidate if candidate in order else None
    # "2025 R2" release spelling -> 25.2
    year = int(match.group("year"))
    rev = int(match.group("rrev"))
    candidate = f"{year - 2000}.{rev}"
    return candidate if candidate in order else None


def _version_index(version: str, ctx_pack: dict[str, Any]) -> int | None:
    try:
        return ctx_pack["order"].index(version)
    except ValueError:
        return None


def _add(
    ctx: FluentContext,
    lines: LineIndex,
    *,
    code: str,
    severity: Severity,
    message: str,
    line: int | None,
    column: int | None = None,
    end_line: int | None = None,
    explanation: str = "",
    suggested_fix: str = "",
    confidence: Confidence = Confidence.MEDIUM,
    is_heuristic: bool = True,
    source_id: str = "",
) -> None:
    line_out, col_out = line, column
    if ctx.mapper is not None and line is not None:
        line_out, col_out = ctx.mapper.map_line_col(line, column or 1)
        explanation = (explanation + " " + ctx.mapper.note).strip() if ctx.mapper.note else explanation
    diag = Diagnostic(
        code=code,
        severity=severity,
        message=message,
        line=line_out,
        column=col_out,
        end_line=end_line,
        confidence=confidence,
        product="fluent",
        dialect="fluent-journal",
        detected_version=ctx.version,
        supported_versions=ctx.supported,
        file_path=ctx.file_path,
        explanation=explanation,
        suggested_fix=suggested_fix,
        is_heuristic=is_heuristic,
    )
    if source_id:
        fields = source(source_id)
        diag.source_id = fields["source_id"]
        diag.source_url = fields["source_url"]
        diag.source_title = fields["source_title"]
    ctx.diagnostics.append(diag)


def _catalog_lookup(cmd: str) -> tuple[dict[str, Any] | None, str]:
    """Return (entry, matched_key). Handles partial menu paths."""
    catalog = load_tui_catalog()["commands"]
    if cmd in catalog:
        return catalog[cmd], cmd
    prefix = cmd + "/"
    for key in catalog:
        if key.startswith(prefix):
            return None, cmd  # valid partial menu navigation, not an entry
    return None, ""


def parse_journal_text(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
    version: str | None = None,
    mapper: CoordMapper | None = None,
) -> list[Diagnostic]:
    """Lint Fluent journal content. ``version`` overrides detection."""
    pack = load_version_pack()
    order: list[str] = list(pack["order"])
    resolved_version = version or options.target_version or default_version()
    if resolved_version not in order:
        resolved_version = default_version()

    ctx = FluentContext(
        options=options,
        version=resolved_version,
        version_index=_version_index(resolved_version, pack) or 0,
        supported=tuple(order),
        file_path=file_path,
        mapper=mapper,
    )
    lines = LineIndex(text)
    gui_prefixes: dict[str, str] = load_tui_catalog()["gui_prefixes"]

    declared_seen = False
    confirm_overwrite_line: int | None = None
    first_write_line: int | None = None
    last_solve_line: int | None = None
    last_output_line: int | None = None
    autosave_frequency_lines: list[int] = []
    exit_lines: list[tuple[int, bool]] = []
    referenced_files: list[tuple[str, int]] = []
    unknown_commands: dict[str, tuple[int, int]] = {}
    prompt_answer_lines = 0
    scheme_depth = 0
    scheme_start_line: int | None = None
    # Persistent Scheme lexer state: strings may span physical lines inside
    # multi-line (%py-exec "...") style blocks.
    scheme_lexer = {"in_string": False, "quote": "", "escaped": False}

    for index in range(1, lines.line_count + 1):
        raw = lines.line_text(index)
        stripped = raw.strip()
        if not stripped:
            continue

        # --- Scheme content -------------------------------------------------
        if scheme_depth > 0 or stripped.startswith("("):
            if scheme_depth == 0:
                scheme_start_line = index
                scheme_lexer["in_string"] = False
                scheme_lexer["quote"] = ""
                scheme_lexer["escaped"] = False
            scheme_depth += _paren_delta_stateful(stripped, scheme_lexer)
            if scheme_depth <= 0:
                scheme_depth = 0
                start = scheme_start_line or index
                block = "\n".join(lines.line_text(no) for no in range(start, index + 1))
                _check_scheme_block(ctx, block, start, lines)
                scheme_start_line = None
            continue

        if stripped.startswith(";"):
            continue  # Scheme-style comment line

        # --- Shell escape ---------------------------------------------------
        if stripped.startswith("!"):
            _add(
                ctx,
                lines,
                code="SECURITY_EXTERNAL_PROCESS",
                severity=Severity.WARNING,
                message=f"Journal executes a shell command ({stripped.split()[0]}).",
                line=index,
                column=1,
                explanation=(
                    "'!' passes the rest of the line to the system shell. On an HPC "
                    "cluster this depends on the node environment and can delete or "
                    "overwrite files outside the job directory."
                ),
                suggested_fix="Remove shell escapes from batch journals or replace them with TUI commands.",
                confidence=Confidence.HIGH,
                is_heuristic=False,
            )
            continue

        # --- TUI command ----------------------------------------------------
        # Journal convention (per the official journaling guide): real menu
        # paths start with '/'. Bare words are answers to interactive prompts
        # of the preceding command (report-definitions/add, monitor setup,
        # yes/no confirmations ...) - replay content, never commands.
        if not stripped.startswith("/"):
            prompt_answer_lines += 1
            continue
        token_match = TUI_TOKEN_RE.match(stripped[1:])
        if token_match is None:
            continue
        token = token_match.group(0)
        cmd = "/" + token.lower()
        rest = stripped[1:][token_match.end() :].strip()

        if cmd == "/file/set-tui-version":
            declared_seen = True
            arg = rest.split()[0] if rest else ""
            normalized = normalize_set_tui_value(arg) if arg else None
            if arg and normalized is None:
                _add(
                    ctx,
                    lines,
                    code="FLUENT_VERSION_UNSUPPORTED",
                    severity=Severity.WARNING,
                    message=f"set-tui-version value '{arg}' is outside the supported packs {', '.join(order)}.",
                    line=index,
                    explanation=(
                        "The linter ships version packs for "
                        f"{', '.join(order)}. The declared value cannot be mapped to one of them."
                    ),
                    suggested_fix=f"Use one of: {', '.join(order)} (default {pack['default_version']}).",
                    confidence=Confidence.HIGH,
                    is_heuristic=False,
                    source_id="ansys-fluent-journal-files-25r2",
                )
            elif normalized:
                ctx.version = normalized
                ctx.version_index = _version_index(normalized, pack) or ctx.version_index
            continue

        if cmd == "/file/confirm-overwrite":
            confirm_overwrite_line = index
            continue

        if cmd.startswith("/file/auto-save/") and cmd != "/file/auto-save/root-name":
            autosave_frequency_lines.append(index)

        entry, _matched = _catalog_lookup(cmd)

        # Catalog-backed availability checks against the selected pack.
        if entry is not None:
            introduced = entry.get("introduced")
            removed = entry.get("removed")
            replaced_by = entry.get("replaced_by")
            if introduced is not None and introduced in order:
                intro_idx = order.index(introduced)
                if ctx.version_index < intro_idx:
                    _add(
                        ctx,
                        lines,
                        code="FLUENT_TUI_ADDED_LATER",
                        severity=Severity.WARNING,
                        message=f"'{cmd}' was introduced in {introduced} but the journal targets {ctx.version}.",
                        line=index,
                        explanation="The selected version pack does not provide this command yet.",
                        suggested_fix=f"Target {introduced} or later via /file/set-tui-version, or avoid '{cmd}'.",
                        confidence=Confidence.HIGH,
                        is_heuristic=False,
                        source_id=str(load_tui_catalog()["source_id"]),
                    )
            if removed is not None and removed in order:
                removed_idx = order.index(removed)
                if ctx.version_index >= removed_idx:
                    fix = f"Use '{replaced_by}' instead." if replaced_by else "Check the migration manual for the replacement."
                    _add(
                        ctx,
                        lines,
                        code="FLUENT_TUI_REMOVED",
                        severity=Severity.ERROR,
                        message=f"'{cmd}' was removed in {removed} (journal targets {ctx.version}).",
                        line=index,
                        explanation="The selected version pack marks this command as removed.",
                        suggested_fix=fix,
                        confidence=Confidence.HIGH,
                        is_heuristic=False,
                        source_id="ansys-fluent-tui-changes-25r2",
                    )

        # Unknown commands: honest low-confidence note, aggregated per unique
        # command so a catalog-partial file does not flood the report.
        if entry is None and not _has_known_children(cmd):
            first_line, count = unknown_commands.get(cmd, (index, 0))
            unknown_commands[cmd] = (first_line, count + 1)

        # GUI-dependent prefixes in unattended runs.
        if options.exec_mode.is_unattended:
            for prefix, why in gui_prefixes.items():
                if cmd.startswith(prefix):
                    _add(
                        ctx,
                        lines,
                        code="FLUENT_GUI_IN_HEADLESS",
                        severity=Severity.WARNING,
                        message=f"'{cmd}' requires graphics/GUI support ({why.rstrip('.')}) but the run is {options.exec_mode.value}.",
                        line=index,
                        explanation=(
                            "In '-g'/'-i' batch execution the GUI pipeline is unavailable; "
                            "graphics commands either fail or need a virtual display."
                        ),
                        suggested_fix="Remove GUI commands from batch journals or run interactively.",
                        confidence=Confidence.MEDIUM,
                        is_heuristic=True,
                        source_id="ansys-fluent-batch-execution-25r2",
                    )
                    break

        # Prompt-prone commands.
        if cmd in load_tui_catalog()["prompt_prone"]:
            args = rest.split()
            if cmd == "/exit" and options.exec_mode.is_unattended and not any(a.lower() == "yes" for a in args):
                _add(
                    ctx,
                    lines,
                    code="FLUENT_INTERACTIVE_PROMPT",
                    severity=Severity.WARNING,
                    message="Bare '/exit' prompts about unsaved data in batch runs.",
                    line=index,
                    explanation="Fluent asks whether to save unsaved data when '/exit' carries no argument.",
                    suggested_fix="End batch journals with '/exit yes'.",
                    confidence=Confidence.HIGH,
                    is_heuristic=False,
                    source_id="ansys-fluent-batch-execution-25r2",
                )
            exit_lines.append((index, bool(args)))

        if cmd in SOLVE_COMMANDS:
            last_solve_line = index
            _check_iteration_count(ctx, lines, cmd, rest, index)

        if cmd in WRITE_COMMANDS or cmd.startswith(EXPORT_PREFIX):
            if first_write_line is None:
                first_write_line = index
            last_output_line = index
        if any(cmd.startswith(rc) for rc in READ_COMMANDS) or cmd in WRITE_COMMANDS:
            args = [a for a in re.findall(r"[^\s'\"]+", rest)]
            for arg in args[:1]:
                if any(ch in arg for ch in "./\\~%") or DRIVE_LETTERish(arg):
                    referenced_files.append((arg, index))
                    for finding in scan_path_literal(
                        arg,
                        target_os=options.target_os,
                        line=index,
                        column=len(stripped) - len(rest) + 1,
                        label="file argument",
                    ):
                        _add(
                            ctx,
                            lines,
                            code=finding.code,
                            severity=finding.severity,
                            message=finding.message,
                            line=index,
                            column=len(stripped) - len(rest) + 1,
                            explanation=finding.explanation,
                            suggested_fix=finding.suggested_fix,
                            confidence=finding.confidence,
                            is_heuristic=finding.is_heuristic,
                        )

    # ---- Whole-file structural checks --------------------------------------
    if not declared_seen and text.strip():
        _add(
            ctx,
            lines,
            code="FLUENT_VERSION_MISSING",
            severity=Severity.INFO,
            message="Journal does not declare a TUI version via /file/set-tui-version.",
            line=1,
            explanation=(
                "Without set-tui-version the journal may change meaning on newer "
                "Fluent releases; declaring the target keeps replay behavior stable."
            ),
            suggested_fix=f"Add '/file/set-tui-version {ctx.version}' as the first command.",
            confidence=Confidence.HIGH,
            is_heuristic=False,
            source_id="ansys-fluent-journal-files-25r2",
        )

    # ---- Aggregated unknown-command notes ------------------------------------
    unknown_severity = Severity.INFO if options.strictness.value == "lenient" else Severity.WARNING
    for cmd, (first_line, count) in sorted(unknown_commands.items()):
        suffix_note = f" (seen {count}x)" if count > 1 else ""
        _add(
            ctx,
            lines,
            code="FLUENT_TUI_UNKNOWN",
            severity=unknown_severity,
            message=f"'{cmd}' is not in the shipped {ctx.version} TUI catalog{suffix_note}.",
            line=first_line,
            explanation=(
                "The shipped catalog covers only well-established commands. This "
                "command may still be valid; verify it against the official TUI "
                "reference for your installed release."
            ),
            suggested_fix="Confirm the exact menu path in the official Fluent TUI documentation.",
            confidence=Confidence.LOW,
            is_heuristic=True,
            source_id="ansys-fluent-tui-25r2",
        )

    if scheme_depth > 0:
        _add(
            ctx,
            lines,
            code="SCHEME_UNBALANCED_PARENS",
            severity=Severity.ERROR,
            message="Scheme expression opened at this line is never closed.",
            line=scheme_start_line or lines.line_count,
            explanation="Parentheses opened in Scheme content must balance before the journal ends.",
            suggested_fix="Close all open parentheses in the Scheme expression.",
            confidence=Confidence.HIGH,
            is_heuristic=False,
        )

    if (
        options.exec_mode.is_unattended
        and first_write_line is not None
        and confirm_overwrite_line is None
    ):
        _add(
            ctx,
            lines,
            code="FLUENT_OVERWRITE_UNSAFE",
            severity=Severity.WARNING,
            message="File writes without overwrite handling in an unattended run.",
            line=first_write_line,
            explanation=(
                "When the target file already exists, Fluent asks whether to overwrite; "
                "in batch mode the prompt stalls or aborts the job."
            ),
            suggested_fix="Add '/file/confirm-overwrite yes' before the first write/export command.",
            confidence=Confidence.MEDIUM,
            is_heuristic=True,
            source_id="ansys-fluent-file-commands-25r2",
        )

    if last_solve_line is not None and last_output_line is None:
        autosave_configured = bool(autosave_frequency_lines)
        _add(
            ctx,
            lines,
            code="FLUENT_NO_OUTPUT",
            severity=Severity.INFO if autosave_configured else Severity.WARNING,
            message="Solving happens but no case/data output follows the last solve command."
            + (" Autosave is configured." if autosave_configured else ""),
            line=last_solve_line,
            explanation=(
                "If the job produces neither explicit write-case/data commands nor "
                "autosave output, solver results are lost when the job ends."
            ),
            suggested_fix=(
                "Add '/file/write-case-data <name>' after solving, or configure "
                "'/file/auto-save/data-frequency' and 'case-frequency'."
            ),
            confidence=Confidence.MEDIUM if not autosave_configured else Confidence.LOW,
            is_heuristic=True,
            source_id="ansys-fluent-batch-execution-25r2",
        )
    elif last_solve_line is not None and last_output_line is not None and last_output_line < last_solve_line:
        _add(
            ctx,
            lines,
            code="FLUENT_NO_OUTPUT",
            severity=Severity.INFO,
            message="The last solve command occurs after the final file output.",
            line=last_solve_line,
            explanation="Results computed after the last write/export are not saved.",
            suggested_fix="Move or repeat the write-case-data command after the final solve step.",
            confidence=Confidence.MEDIUM,
            is_heuristic=True,
            source_id="ansys-fluent-batch-execution-25r2",
        )

    for first_name, second_name, first_line, second_line in case_insensitive_duplicates(referenced_files):
        _add(
            ctx,
            lines,
            code="PORTABILITY_CASE_MISMATCH",
            severity=Severity.WARNING,
            message=f"References differ only by letter case: '{first_name}' vs '{second_name}'.",
            line=second_line,
            explanation=(
                "Linux filesystems are case-sensitive. Two references that differ only "
                "by case address different files and one of them likely does not exist."
            ),
            suggested_fix="Make the file name casing consistent across all references.",
            confidence=Confidence.MEDIUM,
            is_heuristic=False,
        )

    return ctx.diagnostics


def DRIVE_LETTERish(arg: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:", arg))


def _has_known_children(cmd: str) -> bool:
    prefix = cmd + "/"
    return any(key.startswith(prefix) for key in load_tui_catalog()["commands"])


def _paren_delta_stateful(line: str, state: dict) -> int:
    """Per-line paren delta with persistent string/comment state.

    Scheme strings may contain literal newlines (multi-line %py-exec
    payloads), so quote state must survive across lines of one block.
    ``state`` keys: in_string, quote, escaped.
    """
    depth = 0
    for ch in line:
        if state["escaped"]:
            state["escaped"] = False
            continue
        if state["in_string"]:
            if ch == "\\":
                state["escaped"] = True
                continue
            if ch == state["quote"]:
                state["in_string"] = False
            continue
        if ch in "\"'":
            state["in_string"] = True
            state["quote"] = ch
            continue
        if ch == ";":
            break  # Scheme comment: rest of the line is ignored
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
    return depth


def _check_scheme_block(ctx: FluentContext, block: str, start_line: int, lines: LineIndex) -> None:
    lowered = block.lower()
    if "(system " in lowered:
        line_offset = block.lower().index("(system ")
        inner_line = block.count("\n", 0, line_offset) + 1
        _add(
            ctx,
            lines,
            code="SECURITY_EXTERNAL_PROCESS",
            severity=Severity.WARNING,
            message="Scheme '(system ...)' call executes an external program.",
            line=start_line + inner_line - 1,
            explanation=(
                "Scheme system calls hand arbitrary commands to the OS shell; on HPC "
                "compute nodes this is fragile and potentially unsafe."
            ),
            suggested_fix="Avoid shell-outs in batch journals; use TUI/file commands instead.",
            confidence=Confidence.HIGH,
            is_heuristic=False,
        )


def _check_iteration_count(ctx: FluentContext, lines: LineIndex, cmd: str, rest: str, line: int) -> None:
    args = rest.split()
    if not args:
        return
    candidate = args[-1] if cmd == "/solve/dual-time-iterate" and len(args) > 1 else args[0]
    if not candidate.isdigit():
        return
    count = int(candidate)
    if count > 200000:
        _add(
            ctx,
            lines,
            code="HPC_EXCESSIVE_ITERATIONS",
            severity=Severity.INFO,
            message=f"'{cmd} {count}' requests a very large iteration/time-step count.",
            line=line,
            column=1,
            explanation=(
                "Very large static iteration counts multiply wall-time and core-hours; "
                "confirm the number is intentional and covered by the job time limit."
            ),
            suggested_fix="Verify the requested count against the job walltime and convergence needs.",
            confidence=Confidence.LOW,
            is_heuristic=True,
        )


def lint(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
    version: str | None = None,
    mapper: CoordMapper | None = None,
) -> list[Diagnostic]:
    """Public entry point used by the dispatcher and by embedded extraction."""
    return parse_journal_text(
        text,
        options,
        file_path=file_path,
        version=version,
        mapper=mapper,
    )
