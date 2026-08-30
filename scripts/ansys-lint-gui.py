#!/usr/bin/env python3
"""Standalone GUI launcher for the ANSYS Script & Journal Linter.

Opens the same tool page that HPC Client GUI hosts inside the Plugin
Manager - without requiring an installed application. Useful for quick,
visual checks of your own journals.

Usage:
    python scripts/ansys-lint-gui.py [optional initial paths...]

Requires PySide6 (the main application's environment already has it).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _engine_dir() -> Path | None:
    candidates = sorted((REPO_ROOT / "plugins" / "ansys-lint").glob("*/engine"))
    return candidates[-1] if candidates else None


def main() -> int:
    engine = _engine_dir()
    if engine is None:
        print("error: no plugins/ansys-lint/*/engine directory found", file=sys.stderr)
        return 3
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(engine))

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)

    from PySide6.QtWidgets import QDialog, QVBoxLayout

    import ansys_lint

    descriptor = ansys_lint.create_plugin()
    page = descriptor["page_factory"](parent=None, initial_paths=sys.argv[1:])

    dialog = QDialog()
    dialog.setWindowTitle(f"{descriptor['title']} ({descriptor['id']})")
    dialog.resize(1000, 700)
    layout = QVBoxLayout(dialog)
    layout.addWidget(page)
    dialog.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
