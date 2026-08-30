"""Lint orchestration: detection -> dispatch -> results.

This is the stable programmatic API used by the CLI and the GUI page:

    from ansys_lint.api import lint_paths, lint_text

    result = lint_paths(["job.jou"], LintOptions())
    for file_result in result.files:
        for diagnostic in file_result.sorted_diagnostics():
            print(diagnostic.code, diagnostic.line, diagnostic.message)
"""

from __future__ import annotations

import os
from pathlib import Path

from .detection import AUTO_THRESHOLD, LOW_THRESHOLD, detect
from .dialects import get_linter
from .model import (
    Confidence,
    DetectionInfo,
    Diagnostic,
    FileResult,
    LintOptions,
    LintRunResult,
    Severity,
)

SUPPORTED_SUFFIXES = {
    ".jou",
    ".wbjn",
    ".py",
    ".dat",
    ".inp",
    ".mac",
    ".log",
    ".js",
    ".vbs",
    ".mcr",
    ".pre",
    ".ccl",
    ".cse",
    ".cst",
    ".tse",
    ".tst",
    ".rpl",
    ".scscript",
    ".dfjnl",
}

# Folder-scan noise filters: hidden directories, VCS metadata and vendored
# dependency trees never contain Ansys journals.
SKIP_DIRECTORY_NAMES = frozenset(
    {
        "node_modules",
        "__pycache__",
        ".git",
        ".svn",
        ".hg",
        ".venv",
        "venv",
        ".pytest_cache",
        ".ruff_cache",
    }
)


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8", errors="replace")


def _uncertain_diagnostic(
    outcome,
    options: LintOptions,
    file_path: str,
) -> Diagnostic:
    top = ", ".join(f"{c.dialect} ({c.confidence:.2f})" for c in outcome.candidates[:3])
    return Diagnostic(
        code="DETECTION_UNCERTAIN",
        severity=Severity.INFO if outcome.confidence < LOW_THRESHOLD else Severity.WARNING,
        message=(
            "Could not confidently identify the product/dialect; no dialect "
            "diagnostics were produced."
            + (f" Closest candidates: {top}." if top else "")
        ),
        line=1,
        confidence=Confidence.MEDIUM,
        product=outcome.product,
        dialect=outcome.dialect,
        detected_version=options.target_version,
        supported_versions=(),
        file_path=file_path,
        explanation=(
            "Ambiguous formats (.py/.dat/.log/.js) are only linted when detection "
            "is confident or an explicit dialect override is given. This protects "
            "you from floods of false positives."
        ),
        suggested_fix="Select the dialect/product manually in the GUI or pass --dialect on the CLI.",
        is_heuristic=True,
    )


def _unsupported_note(file_path: str) -> FileResult:
    return FileResult(
        file_path=file_path,
        detection=DetectionInfo(product="unknown", dialect="unknown"),
        diagnostics=[
            Diagnostic(
                code="FORMAT_UNSUPPORTED",
                severity=Severity.WARNING,
                message="File format is not recognized as any supported Ansys script/journal type.",
                line=1,
                file_path=file_path,
                explanation="No detector produced a plausible candidate.",
                suggested_fix="Check the file extension/content, or select a dialect manually.",
                confidence=Confidence.LOW,
                is_heuristic=True,
            )
        ],
    )


def lint_text(
    text: str,
    *,
    file_name: str = "",
    options: LintOptions | None = None,
) -> FileResult:
    """Detect and lint one in-memory document (GUI editor path)."""
    options = options or LintOptions()
    outcome = detect(file_name, text, options.launch_command)

    dialect_key = outcome.dialect
    if options.dialect_override:
        dialect_key = options.dialect_override

    detection_info = DetectionInfo(
        product=outcome.product if outcome.confidence >= LOW_THRESHOLD and not options.dialect_override else (
            dialect_key.split("-")[0] if options.dialect_override else "unknown"
        ),
        dialect=dialect_key,
        detected_version=outcome.detected_version
        or (options.target_version if dialect_key == "fluent" else ""),
        supported_versions=_supported_versions_for(dialect_key),
        confidence=outcome.confidence,
        evidence=outcome.evidence,
    )

    result = FileResult(file_path=file_name, detection=detection_info)

    if dialect_key in ("unknown", "__generic_python__") and not options.force:
        result.diagnostics.append(_uncertain_diagnostic(outcome, options, file_name))
        return result

    if outcome.confidence < AUTO_THRESHOLD and not options.dialect_override and not options.force:
        result.diagnostics.append(_uncertain_diagnostic(outcome, options, file_name))
        return result

    linter = get_linter(dialect_key)
    kwargs = {}
    try:
        diagnostics = linter(text, options, file_path=file_name)
    except TypeError:
        # some linters take mapper-only keyword sets
        kwargs["mapper"] = None
        diagnostics = linter(text, options, file_path=file_name)
    del kwargs
    result.diagnostics.extend(diagnostics)
    return result


def _supported_versions_for(dialect: str) -> tuple[str, ...]:
    if dialect == "fluent":
        from .dialects.fluent import supported_versions

        return supported_versions()
    return ()


def lint_file(path: str | Path, options: LintOptions | None = None) -> FileResult:
    path = Path(path)
    options = options or LintOptions()
    text = _read_text(path)
    return lint_text(text, file_name=str(path), options=options)


def _is_skipped_dir(name: str) -> bool:
    return name.startswith(".") or name in SKIP_DIRECTORY_NAMES


def collect_files(paths: list[str | Path], recursive: bool = True) -> list[Path]:
    files: list[Path] = []
    for entry in paths:
        entry_path = Path(entry)
        if entry_path.is_dir():
            if recursive:
                for root, dirs, names in os.walk(entry_path):
                    # Prune hidden/vendor directories so the walker never
                    # descends into them (huge dependency trees stay cheap).
                    dirs[:] = sorted(d for d in dirs if not _is_skipped_dir(d))
                    for name in sorted(names):
                        candidate = Path(root) / name
                        if candidate.suffix.lower() in SUPPORTED_SUFFIXES:
                            files.append(candidate)
            else:
                for candidate in sorted(entry_path.iterdir()):
                    if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_SUFFIXES:
                        files.append(candidate)
        elif entry_path.is_file():
            files.append(entry_path)
    seen: set[str] = set()
    unique: list[Path] = []
    for item in files:
        key = str(item.resolve()).lower() if os.name == "nt" else str(item.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def lint_paths(
    paths: list[str | Path],
    options: LintOptions | None = None,
    *,
    recursive: bool = True,
) -> LintRunResult:
    """Lint files and/or folders. Never raises for per-file problems."""
    options = options or LintOptions()
    run = LintRunResult()
    for path in collect_files(paths, recursive=recursive):
        try:
            run.files.append(lint_file(path, options))
        except OSError as exc:
            run.files.append(
                FileResult(
                    file_path=str(path),
                    diagnostics=[
                        Diagnostic(
                            code="FILE_READ_ERROR",
                            severity=Severity.ERROR,
                            message=f"Cannot read file: {exc}",
                            file_path=str(path),
                            confidence=Confidence.HIGH,
                            is_heuristic=False,
                        )
                    ],
                )
            )
    return run
