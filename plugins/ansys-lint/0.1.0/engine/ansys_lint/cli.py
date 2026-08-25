"""Headless command-line interface.

Exit codes:
    0  success - no findings at/above the failure threshold
    1  lint findings at/above the configured threshold
    2  unsupported or undetected format (at least one input)
    3  internal failure (unexpected engine error)

Examples:
    ansys-journal-lint path/to/file.jou
    ansys-journal-lint folder --version 25.2 --target linux --mode batch
    ansys-journal-lint file.wbjn --format json
    ansys-journal-lint file.dat --dialect mapdl
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback

from . import ENGINE_VERSION, __version__
from .detection import detect
from .dialects import DIALECT_LABELS, known_dialects
from .model import LintOptions, ExecMode, Severity, Strictness, TargetOS
from .api import lint_paths, collect_files

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_UNDETECTED = 2
EXIT_INTERNAL = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ansys-journal-lint",
        description=(
            "Unofficial offline linter for Ansys script/journal formats "
            "(Fluent journals, Workbench .wbjn, MAPDL inputs, CCL sessions, "
            "ICEM replays, System Coupling scripts and more)."
        ),
    )
    parser.add_argument("paths", nargs="*", help="Files and/or folders to lint.")
    parser.add_argument(
        "--version",
        default=None,
        help="Ansys target version pack id, e.g. 24.2 | 25.1 | 25.2 | 26.1 (default: 25.2).",
    )
    parser.add_argument("--dialect", default=None, help=f"Dialect override: {', '.join(known_dialects())}.")
    parser.add_argument(
        "--mode",
        choices=[m.value for m in ExecMode],
        default=ExecMode.BATCH.value,
        help="Execution mode of the surrounding run (default: batch).",
    )
    parser.add_argument(
        "--target",
        choices=[t.value for t in TargetOS],
        default=TargetOS.LINUX.value,
        help="Target operating system for portability checks (default: linux).",
    )
    parser.add_argument(
        "--strictness",
        choices=[s.value for s in Strictness],
        default=Strictness.LENIENT.value,
        help="Unknown-command strictness, mainly for MAPDL (default: lenient).",
    )
    parser.add_argument(
        "--launch-command",
        default="",
        help='Surrounding launch command when known, e.g. "fluent 3ddp -g -i job.jou".',
    )
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    parser.add_argument(
        "--fail-on",
        choices=["none", "info", "warning", "error"],
        default="error",
        help="Severity that produces exit code 1 (default: error).",
    )
    parser.add_argument("--no-recursive", action="store_true", help="Do not recurse into folders.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Lint even when detection confidence is low (best effort).",
    )
    parser.add_argument("--list-dialects", action="store_true", help="List supported dialects and exit.")
    return parser


def _options_from_args(args) -> LintOptions:
    return LintOptions(
        target_version=args.version or "25.2",
        exec_mode=ExecMode(args.mode),
        target_os=TargetOS(args.target),
        strictness=Strictness(args.strictness),
        dialect_override=args.dialect,
        launch_command=args.launch_command,
        force=args.force,
    )


def render_text(run) -> str:
    lines: list[str] = []
    totals = {"error": 0, "warning": 0, "info": 0}
    for file_result in sorted(run.files, key=lambda f: f.file_path):
        header = file_result.file_path or "<memory>"
        detection = file_result.detection
        meta = []
        if detection.product != "unknown":
            meta.append(f"product={detection.product}")
        if detection.dialect != "unknown":
            meta.append(f"dialect={detection.dialect}")
        if detection.detected_version:
            meta.append(f"version={detection.detected_version}")
        meta.append(f"confidence={detection.confidence:.2f}")
        lines.append(f"{header}  [{', '.join(meta)}]")
        if not file_result.diagnostics:
            lines.append("  no findings")
        for diag in file_result.sorted_diagnostics():
            location = "?:?" if diag.line is None else f"{diag.line}:{diag.column or 1}"
            flags = []
            if diag.is_heuristic:
                flags.append("heuristic")
            if diag.source_url:
                flags.append(f"source={diag.source_url}")
            suffix = f"  ({', '.join(flags)})" if flags else ""
            lines.append(
                f"  [{location}] {diag.severity.value.upper():7s} {diag.code}: {diag.message}{suffix}"
            )
            if diag.suggested_fix:
                lines.append(f"           fix: {diag.suggested_fix}")
        lines.append("")
        summary = file_result.summary
        for key in totals:
            totals[key] += summary[key]
    lines.append(
        f"Summary: {totals['error']} error(s), {totals['warning']} warning(s), {totals['info']} info"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    # Journals frequently carry non-ASCII comments (e.g. Turkish); never let
    # a legacy console codepage crash the report.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):  # pragma: no cover - exotic streams
                pass

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_dialects:
        for key in known_dialects():
            print(f"{key}\t{DIALECT_LABELS.get(key, '')}")
        return EXIT_OK

    if not args.paths:
        parser.print_usage(sys.stderr)
        print("error: at least one path is required", file=sys.stderr)
        return EXIT_INTERNAL

    options = _options_from_args(args)

    try:
        files = collect_files([args.paths[0]] if False else args.paths, recursive=not args.no_recursive)
        if not files:
            print("No lintable files found.", file=sys.stderr)
            return EXIT_UNDETECTED
        undetected = False
        for path in files:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            outcome = detect(str(path), text, options.launch_command)
            if outcome.confidence < 0.35 and not options.dialect_override and not options.force:
                undetected = True
        run = lint_paths(args.paths, options, recursive=not args.no_recursive)
    except Exception:  # pragma: no cover - defensive boundary
        traceback.print_exc()
        return EXIT_INTERNAL

    threshold_rank = {"none": -1, "info": Severity.INFO.rank, "warning": Severity.WARNING.rank, "error": Severity.ERROR.rank}[args.fail_on]
    blocking = any(
        diag.severity.rank >= threshold_rank
        for result in run.files
        for diag in result.diagnostics
    ) if threshold_rank >= 0 else False

    if args.format == "json":
        payload = {
            "tool": "ansys-journal-lint",
            "engine_version": ENGINE_VERSION,
            "plugin_version": __version__,
            "options": {
                "target_version": options.target_version,
                "mode": options.exec_mode.value,
                "target_os": options.target_os.value,
                "strictness": options.strictness.value,
                "dialect": options.dialect_override,
            },
            "files": [
                {
                    "path": result.file_path,
                    "detection": result.detection.to_dict(),
                    "summary": result.summary,
                    "diagnostics": [diag.to_dict() for diag in result.sorted_diagnostics()],
                }
                for result in run.files
            ],
            "summary": run.summary,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(render_text(run))

    if blocking:
        return EXIT_FINDINGS
    if undetected:
        return EXIT_UNDETECTED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
