"""ANSYS Script & Journal Linter - unofficial offline linter engine.

Public API::

    from ansys_lint import lint_paths, lint_text, detect, LintOptions

    result = lint_paths(["job.jou"], LintOptions())
    print(result.summary)

The engine is pure standard-library Python and runs fully offline. It
ships inside the ``org.hpcclient.ansyslint`` plugin package for the HPC
Client GUI plugin system (Plugin API v2, capability ``linter-tool``).

This plugin is NOT affiliated with or endorsed by Ansys, Inc.
"""

from __future__ import annotations

from .model import (
    ENGINE_VERSION,
    Confidence,
    CoordMapper,
    DetectionInfo,
    Diagnostic,
    ExecMode,
    FileResult,
    LintOptions,
    LintRunResult,
    Severity,
    Strictness,
    TargetOS,
)

__version__ = ENGINE_VERSION

__all__ = [
    "ENGINE_VERSION",
    "__version__",
    "Confidence",
    "CoordMapper",
    "DetectionInfo",
    "Diagnostic",
    "ExecMode",
    "FileResult",
    "LintOptions",
    "LintRunResult",
    "Severity",
    "Strictness",
    "TargetOS",
    "detect",
    "lint_file",
    "lint_paths",
    "lint_text",
]


def __getattr__(name: str):
    # Lazy re-exports keep GUI-free imports light.
    if name == "lint_paths":
        from .api import lint_paths

        return lint_paths
    if name == "lint_text":
        from .api import lint_text

        return lint_text
    if name == "lint_file":
        from .api import lint_file

        return lint_file
    if name == "detect":
        from .detection import detect

        return detect
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def create_plugin():
    """Plugin API v2 entry point (called by the host application loader).

    Returns a tool descriptor consumed by the Plugin Manager UI. The Qt
    page factory imports PySide6 lazily so headless environments never
    need Qt.
    """
    return {
        "id": "org.hpcclient.ansyslint",
        "title": "ANSYS Script & Journal Linter",
        "description": (
            "Offline structural, catalog-backed and heuristic checks for Ansys "
            "journals across Fluent, MAPDL, Workbench, CCL products, ICEM, "
            "System Coupling and more."
        ),
        "page_factory": _create_page_factory(),
        "cli": "ansys_lint.cli",
    }


def _create_page_factory():
    def factory(parent=None, initial_paths=None):
        from .qt_page import build_page

        return build_page(parent=parent, initial_paths=initial_paths)

    return factory


def main(argv: list[str] | None = None) -> int:
    """Console entry point."""
    from .cli import main as cli_main

    return cli_main(argv)
