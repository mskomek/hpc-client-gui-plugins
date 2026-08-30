"""Ansys Workbench journal linter (.wbjn and Workbench-oriented .py).

A Workbench journal is Python-based, but native commands travel to
integrated applications through ``SendCommand()`` strings whose language
depends on the target container (Fluent TUI/Scheme, CCL, APDL, JScript,
Python...). This module:

1. parses the OUTER Python journal structurally (AST - exact);
2. tracks ``GetTemplate`` / ``CreateSystem`` / ``GetSystem`` assignments so
   the target application of each container variable is known;
3. extracts every ``SendCommand(Command=..., Language=...)`` literal while
   keeping a per-character map back into the outer file;
4. decides the embedded dialect from (in order) the explicit ``Language=``
   argument, the resolved container, and finally command signatures;
5. re-lints embedded content with the matching dialect parser and remaps
   every diagnostic back to the correct outer line/column;
6. applies Workbench-level checks (interactive editor dependency in batch,
   path portability of all literals, runwb2 -B pattern, SetScriptVersion).

Generic ``.py`` files are NOT treated as Workbench journals here - that
decision belongs to the detector registry (see detection.py).
"""

from __future__ import annotations

import ast
import re

from ..embedded import LiteralExtractor, LiteralSpanOffsetter, iter_sendcommand_calls, keyword_args, positional_strings
from ..model import Confidence, CoordMapper, Diagnostic, LintOptions, Severity
from ..rules_common import scan_path_literal
from ..sources import resolve as source
from ..textlines import LineIndex

WB_COMMAND_NAMES = frozenset(
    {
        "GetTemplate",
        "CreateSystem",
        "GetSystem",
        "GetContainer",
        "Update",
        "Save",
        "Edit",
        "Exit",
        "SendCommand",
        "SetScriptVersion",
    }
)

# Container label (lower-cased substring match) -> default embedded dialect.
CONTAINER_DIALECTS: tuple[tuple[str, str], ...] = (
    ("fluent", "fluent"),
    ("cfd-post", "ccl"),
    ("cfdpost", "ccl"),
    ("cfx", "ccl"),
    ("turbo", "ccl"),
    ("mechanical apdl", "mapdl"),
    ("apdl", "mapdl"),
    ("mechanical", "mechanical"),
    ("mesh", "jscript-meshing"),
    ("design model", "dm-jscript"),
    ("aqwa", "aqwa-jscript"),
    ("spaceclaim", "spaceclaim"),
    ("discovery", "spaceclaim"),
    ("engineering data", "jscript-generic"),
)

LANGUAGE_DIALECTS: dict[str, str] = {
    "python": "python-explicit",
    "jscript": "jscript-explicit",
    "javascript": "jscript-explicit",
    "apdl": "mapdl",
    "mapdl": "mapdl",
    "ccl": "ccl",
    "tui": "fluent",
    "fluent tui": "fluent",
    "scheme": "fluent",
}

PROJECT_PATH_RE = ".wbpj"


def sniff_embedded_dialect(content: str) -> tuple[str, Confidence]:
    """Signature-based fallback when neither Language nor container helps."""
    stripped = content.strip()
    if not stripped:
        return "unknown", Confidence.LOW
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    first = lines[0]

    # CCL object headers or END terminators.
    ccl_header = 0
    for line in lines[:30]:
        if line.upper() == "END":
            ccl_header += 1
        elif ":" in line and "=" not in line and not line.startswith(">") and len(line) < 80:
            ccl_header += 1
    if ccl_header >= 2:
        return "ccl", Confidence.HIGH

    # APDL vs Fluent TUI disambiguation.
    # APDL processors are single ALL-UPPERCASE slash tokens (/PREP7);
    # TUI commands are lowercase multi-segment paths (/file/read-case).
    apdl_slash = sum(1 for line in lines[:40] if re.fullmatch(r"/[A-Z0-9]+", line))
    tui_paths = sum(
        1 for line in lines[:20]
        if re.match(r"^/[a-z][a-z0-9\-]*(/[a-z0-9\-]+)+", line)
    )
    if "set-tui-version" in stripped[:400]:
        return "fluent", Confidence.HIGH
    apdl_plain = 0
    for line in lines[:40]:
        token = line.split(",")[0].split()[0] if line.split() else ""
        if token.isupper() and 2 <= len(token) <= 10 and token.replace("_", "").isalpha():
            apdl_plain += 1
    if apdl_slash >= 1 or apdl_plain >= 2:
        if tui_paths == 0 or apdl_slash + apdl_plain > tui_paths * 3:
            return "mapdl", Confidence.MEDIUM
    if tui_paths >= 1:
        return "fluent", Confidence.HIGH

    # Scheme: starts with a paren and is parenthesis heavy.
    if first.startswith("("):
        parens = stripped.count("(") + stripped.count(")")
        if parens >= 4:
            return "fluent", Confidence.MEDIUM  # scheme handled by fluent parser

    if "agb." in stripped:
        return "dm-jscript", Confidence.HIGH
    if "ExtAPI" in stripped or "DataModel" in stripped:
        return "mechanical", Confidence.HIGH
    if "oDesktop" in stripped or "oProject" in stripped:
        return "aedt", Confidence.MEDIUM
    python_hints = sum(
        1 for line in lines[:20]
        if line.startswith(("def ", "import ", "from ", "print(", "#"))
    )
    if python_hints >= 1:
        return "generic-python", Confidence.MEDIUM
    jscript_hints = sum(
        1 for line in lines[:20]
        if line.startswith(("var ", "function ")) or line.endswith(";")
    )
    if jscript_hints >= 2:
        return "jscript-generic", Confidence.MEDIUM
    return "unknown", Confidence.LOW


def _container_from_call(node: ast.Call) -> str | None:
    """Extract template/system/container label from WB factory calls."""
    kwargs = keyword_args(node)
    for key in ("Template", "Name"):
        value = kwargs.get(key)
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    for arg in positional_strings(node):
        return arg.value
    return None


def _receiver_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Attribute):
        base = func.value
        while isinstance(base, ast.Attribute):
            base = base.value
        if isinstance(base, ast.Name):
            return base.id
    return None


def lint(
    text: str,
    options: LintOptions,
    *,
    file_path: str = "",
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    # ---- Outer Python syntax -------------------------------------------------
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        diagnostics.append(
            Diagnostic(
                code="WB_PYTHON_SYNTAX",
                severity=Severity.ERROR,
                message=f"Workbench journal has a Python syntax error: {exc.msg}",
                line=exc.lineno or 1,
                column=exc.offset or 1,
                product="workbench",
                dialect="workbench-python",
                detected_version=options.target_version,
                file_path=file_path,
                explanation="The journal must parse as Python before deeper checks can run.",
                suggested_fix="Fix the reported syntax error; embedded SendCommand analysis was skipped.",
                confidence=Confidence.HIGH,
                is_heuristic=False,
            )
        )
        return diagnostics

    extractor = LiteralExtractor(text)

    def add_outer(
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
            product="workbench",
            dialect="workbench-python",
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

    # ---- Container tracking ----------------------------------------------------
    containers: dict[str, str] = {}
    declared_version: str | None = None

    class OuterVisitor(ast.NodeVisitor):
        def visit_Assign(self, node: ast.Assign) -> None:
            value = node.value
            label: str | None = None
            if isinstance(value, ast.Call):
                name = getattr(value.func, "id", getattr(value.func, "attr", ""))
                if str(name) in ("GetTemplate", "CreateSystem", "GetSystem"):
                    label = _container_from_call(value)
                elif str(name) == "GetContainer":
                    # Inherit the container label from the receiver variable.
                    base = _receiver_name(value)
                    if base:
                        label = containers.get(base)
            elif isinstance(value, ast.Name):
                # Variable-to-variable propagation (system = template).
                label = containers.get(value.id)
            if label:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        containers[target.id] = label
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            name = getattr(node.func, "id", getattr(node.func, "attr", ""))
            if str(name) == "SetScriptVersion":
                kwargs = keyword_args(node)
                value = kwargs.get("Version")
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    nonlocal declared_version
                    declared_version = value.value
            if str(name) == "Edit" and options.exec_mode.value != "interactive":
                add_outer(
                    code="WB_INTERACTIVE_EDIT",
                    severity=Severity.WARNING,
                    message="Edit() opens an interactive editor but this run is unattended.",
                    line=node.lineno,
                    column=node.col_offset + 1,
                    explanation=(
                        "runwb2 -B executes without user interaction; Edit() waits for "
                        "a GUI that never appears or returns immediately without effect."
                    ),
                    suggested_fix="Remove Edit() calls from batch journals.",
                    confidence=Confidence.MEDIUM,
                    is_heuristic=True,
                    source_id="ansys-wb-cmdline-25r2",
                )
            self.generic_visit(node)

    OuterVisitor().visit(tree)

    # ---- SendCommand extraction + nested linting -------------------------------
    from . import ccl as ccl_module
    from . import fluent as fluent_module
    from . import mapdl as mapdl_module
    from .. import jscript as jscript_module

    def decide_dialect(language_arg: str | None, container: str | None, content: str) -> tuple[str, Confidence]:
        if language_arg:
            key = LANGUAGE_DIALECTS.get(language_arg.strip().lower())
            if key:
                return key, Confidence.HIGH
        if container:
            lowered = container.lower()
            for marker, dialect_key in CONTAINER_DIALECTS:
                if marker in lowered:
                    return dialect_key, Confidence.MEDIUM
        return sniff_embedded_dialect(content)

    def ccl_product_for(container: str | None, content: str) -> str:
        if container:
            lowered = container.lower()
            if "turbo" in lowered:
                return "turbo-grid"
            if "cfd-post" in lowered or "cfdpost" in lowered or "post" in lowered:
                return "cfd-post"
            if "cfx" in lowered:
                return "cfx"
        if ">quit" in content or ">load" in content:
            return "cfd-post"
        return "cfx"

    def lint_embedded(
        dialect_key: str,
        content: str,
        mapper: CoordMapper,
        call_line: int,
        container: str | None = None,
    ) -> list[Diagnostic]:
        product_for = {
            "fluent": "fluent",
            "ccl": "cfx",
            "mapdl": "mapdl",
            "mechanical": "mechanical",
            "dm-jscript": "designmodeler",
            "aqwa-jscript": "aqwa",
            "jscript-meshing": "meshing",
            "jscript-explicit": "workbench",
            "jscript-generic": "workbench",
            "python-explicit": "workbench",
            "generic-python": "workbench",
            "spaceclaim": "spaceclaim",
            "aedt": "aedt",
        }.get(dialect_key, "workbench")

        if dialect_key == "fluent":
            return fluent_module.lint(
                content,
                options,
                file_path=file_path,
                version=options.target_version,
                mapper=mapper,
            )
        if dialect_key == "mapdl":
            return mapdl_module.lint(content, options, file_path=file_path) if mapper is None else \
                _mapped_mapdl(content, options, mapper)
        if dialect_key == "ccl":
            kind = "session" if ">" in content else "state"
            return ccl_module.lint(
                content,
                options,
                file_path=file_path,
                product=ccl_product_for(container, content),
                kind=kind,
                mapper=mapper,
            )
        if dialect_key in (
            "jscript-meshing",
            "jscript-explicit",
            "jscript-generic",
            "dm-jscript",
            "aqwa-jscript",
        ):
            diags, literals = jscript_module.lint_jscript(
                content,
                options,
                file_path=file_path,
                product=product_for,
                dialect=dialect_key,
                mapper=mapper,
            )
            # portability on extracted string literals
            for value, inner_line, inner_col in literals:
                for finding in scan_path_literal(
                    value,
                    target_os=options.target_os,
                    line=inner_line,
                    column=inner_col,
                    label="string literal",
                ):
                    out_line, out_col = mapper.map_line_col(inner_line, inner_col)
                    diags.append(
                        Diagnostic(
                            code=finding.code,
                            severity=finding.severity,
                            message=finding.message,
                            line=out_line,
                            column=out_col,
                            product=product_for,
                            dialect=dialect_key,
                            detected_version=options.target_version,
                            file_path=file_path,
                            explanation=finding.explanation,
                            suggested_fix=finding.suggested_fix,
                            confidence=finding.confidence,
                            is_heuristic=finding.is_heuristic,
                        )
                    )
            return diags
        if dialect_key in ("mechanical", "python-explicit", "generic-python", "spaceclaim", "aedt"):
            return _lint_python_snippet(content, options, file_path, product_for, mapper)
        # Unknown: single honest diagnostic at the call site.
        add_outer(
            code="WB_EMBEDDED_LANGUAGE_UNKNOWN",
            severity=Severity.WARNING,
            message=f"Could not determine the embedded language of SendCommand at line {call_line}.",
            line=call_line,
            explanation=(
                "Neither the Language argument, the target container nor command "
                "signatures identified the payload. No nested validation was run."
            ),
            suggested_fix='Add Language="..." to the SendCommand call so the linter can check it.',
            confidence=Confidence.LOW,
            is_heuristic=True,
        )
        return []

    def _mapped_mapdl(content: str, opts: LintOptions, mapper: CoordMapper) -> list[Diagnostic]:
        raw = mapdl_module.lint(content, opts, file_path=file_path)
        mapped: list[Diagnostic] = []
        note = f" {mapper.note}" if mapper.note else ""
        for diag in raw:
            new_line = new_col = None
            if diag.line is not None:
                new_line, new_col = mapper.map_line_col(diag.line, diag.column or 1)
            mapped.append(
                Diagnostic(
                    code=diag.code,
                    severity=diag.severity,
                    message=(diag.message + note).strip(),
                    line=new_line,
                    column=new_col,
                    end_line=diag.end_line,
                    end_column=diag.end_column,
                    confidence=diag.confidence,
                    product=diag.product,
                    dialect=diag.dialect,
                    detected_version=diag.detected_version,
                    supported_versions=diag.supported_versions,
                    file_path=diag.file_path,
                    explanation=diag.explanation,
                    suggested_fix=diag.suggested_fix,
                    source_id=diag.source_id,
                    source_url=diag.source_url,
                    source_title=diag.source_title,
                    is_heuristic=diag.is_heuristic,
                )
            )
        return mapped

    def _lint_python_snippet(
        content: str,
        opts: LintOptions,
        path: str,
        product_for: str,
        mapper: CoordMapper | None,
    ) -> list[Diagnostic]:
        """Honest structural-only check for embedded Python payloads.

        Generic Python syntax validation NEVER proves Mechanical/SpaceClaim/
        AEDT API validity - documented limitation, see docs/coverage.md.
        """
        result: list[Diagnostic] = []
        try:
            ast.parse(content)
        except SyntaxError as exc:
            inner_line, inner_col = exc.lineno or 1, exc.offset or 1
            out_line, out_col = (
                mapper.map_line_col(inner_line, inner_col) if mapper else (inner_line, inner_col)
            )
            note = f" {mapper.note}" if mapper and mapper.note else ""
            result.append(
                Diagnostic(
                    code="PYTHON_SYNTAX_ERROR",
                    severity=Severity.ERROR,
                    message=f"Embedded Python has a syntax error: {exc.msg}{note}".strip(),
                    line=out_line,
                    column=out_col,
                    product=product_for,
                    dialect="python",
                    detected_version=opts.target_version,
                    file_path=path,
                    explanation="The payload passed to SendCommand does not parse as Python.",
                    suggested_fix="Fix the Python syntax inside the command string.",
                    confidence=Confidence.HIGH,
                    is_heuristic=False,
                )
            )
        # portability scan over plain string constants inside the snippet
        snippet_lines = LineIndex(content)
        for node in ast.walk(ast.parse(content) if content.strip() else ast.Module(body=[], type_ignores=[])):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for finding in scan_path_literal(
                    node.value,
                    target_os=opts.target_os,
                    line=node.lineno or 1,
                    column=node.col_offset + 1,
                    label="string literal",
                ):
                    out_line, out_col = (
                        mapper.map_line_col(node.lineno or 1, node.col_offset + 1)
                        if mapper
                        else (node.lineno or 1, node.col_offset + 1)
                    )
                    result.append(
                        Diagnostic(
                            code=finding.code,
                            severity=finding.severity,
                            message=finding.message,
                            line=out_line,
                            column=out_col,
                            product=product_for,
                            dialect="python",
                            detected_version=opts.target_version,
                            file_path=path,
                            explanation=finding.explanation,
                            suggested_fix=finding.suggested_fix,
                            confidence=finding.confidence,
                            is_heuristic=finding.is_heuristic,
                        )
                    )
        del snippet_lines
        return result

    for call in iter_sendcommand_calls(tree):
        kwargs = keyword_args(call)
        command_expr = kwargs.get("Command")
        span: LiteralSpanOffsetter | None = None
        if command_expr is not None:
            span = extractor.from_expression(command_expr)
        else:
            strings = positional_strings(call)
            if strings:
                span = extractor.from_expression(strings[0])
        if span is None or not span.span.value.strip():
            continue

        language_value: str | None = None
        lang_expr = kwargs.get("Language")
        if isinstance(lang_expr, ast.Constant) and isinstance(lang_expr.value, str):
            language_value = lang_expr.value
        container = None
        receiver = _receiver_name(call)
        if receiver:
            container = containers.get(receiver)
        call_line = call.lineno

        def make_mapper(span: LiteralSpanOffsetter, call_line: int) -> CoordMapper:
            def map_line_col(inner_line: int, inner_column: int) -> tuple[int, int]:
                pos = span.outer(inner_line, inner_column)
                if pos is None:
                    return call_line, 1
                return pos

            return CoordMapper(map_line_col=map_line_col, note=f"(embedded SendCommand content, outer line {call_line})")

        mapper = make_mapper(span, call_line)
        dialect_key, _dialect_confidence = decide_dialect(language_value, container, span.span.value)
        for diag in lint_embedded(dialect_key, span.span.value, mapper, call_line, container):
            diagnostics.append(diag)

    # ---- Whole-file portability on remaining literals ---------------------------
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            lowered = value.lower()
            if PROJECT_PATH_RE in lowered or "\\%" in value or DRIVE_RE.match(value):
                for finding in scan_path_literal(
                    value,
                    target_os=options.target_os,
                    line=node.lineno or 1,
                    column=node.col_offset + 1,
                    label="literal",
                ):
                    add_outer(
                        code=finding.code,
                        severity=finding.severity,
                        message=finding.message,
                        line=node.lineno or 1,
                        column=node.col_offset + 1,
                        explanation=finding.explanation,
                        suggested_fix=finding.suggested_fix,
                        confidence=finding.confidence,
                        is_heuristic=finding.is_heuristic,
                    )

    # ---- Version declaration ------------------------------------------------------
    if declared_version:
        normalized = _normalize_wb_version(declared_version)
        supported = options.target_version
        if normalized and supported and normalized != supported:
            add_outer(
                code="WB_VERSION_MISMATCH",
                severity=Severity.INFO,
                message=f"Journal declares version {declared_version} but the selected target is {supported}.",
                line=None,
                explanation=(
                    "SetScriptVersion pins the Workbench release used for replay. "
                    "The selected linter target differs, so version-specific rules "
                    "may not match exactly."
                ),
                suggested_fix=f"Select {declared_version} as the linter target or update SetScriptVersion.",
                confidence=Confidence.MEDIUM,
                is_heuristic=False,
            )

    # ---- Launch pattern -----------------------------------------------------------------
    launch = options.launch_command.lower()
    if launch and "runwb2" in launch and options.exec_mode.value != "interactive":
        if "-b" not in launch.split():
            flags = launch.replace(";", " ").split()
            if "runwb2" in flags and "-b" not in flags:
                add_outer(
                    code="WB_BATCH_FLAG_MISSING",
                    severity=Severity.WARNING,
                    message="Launch uses runwb2 without -B although the run is unattended.",
                    line=None,
                    explanation="Without -B, runwb2 opens the interactive Workbench GUI.",
                    suggested_fix="Use 'runwb2 -B -R script.wbjn' for headless replay.",
                    confidence=Confidence.MEDIUM,
                    is_heuristic=False,
                    source_id="ansys-wb-cmdline-25r2",
                )

    return diagnostics


DRIVE_RE = re.compile(r"[A-Za-z]:[\\/]")


def _normalize_wb_version(raw: str) -> str | None:
    parts = raw.strip().split(".")
    if len(parts) == 2 and all(p.isdigit() for p in parts):
        return f"{parts[0]}.{parts[1]}"
    return None


def signature_score(file_name: str, text: str) -> tuple[float, list[str]]:
    """Detector support: how Workbench-like is this text?"""
    score = 0.0
    evidence: list[str] = []
    lowered_ext = file_name.lower()
    if lowered_ext.endswith(".wbjn"):
        score += 0.55
        evidence.append("extension .wbjn")
    hit = False
    for name in WB_COMMAND_NAMES:
        if re.search(rf"\b{name}\s*\(", text):
            hit = True
            evidence.append(f"calls {name}(")
    if hit:
        score += 0.35
    if "SetScriptVersion" in text:
        score += 0.1
    if re.search(r"\bsendcommand\s*\(", text, re.IGNORECASE) and not hit:
        score += 0.15
        evidence.append("SendCommand( present")
    return min(score, 0.99), evidence
