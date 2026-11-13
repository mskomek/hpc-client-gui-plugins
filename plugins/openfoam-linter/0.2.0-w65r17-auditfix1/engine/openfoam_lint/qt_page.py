"""Optional Qt page for an application explicitly running the Qt runtime."""
from __future__ import annotations

from pathlib import Path

from hpc_gui.core.i18n import t

from .api import lint_paths


def create_qt_page(parent=None, *, initial_paths=(), session_state=None):
    from PySide6.QtWidgets import (
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QPlainTextEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    widget = QWidget(parent)
    layout = QVBoxLayout(widget)
    status = QLabel(t("openfoam.static_only"))
    paths = QListWidget()
    for path in initial_paths:
        paths.addItem(str(path))
    output = QPlainTextEdit()
    output.setReadOnly(True)
    actions = QHBoxLayout()
    add_file = QPushButton(t("openfoam.add_file"))
    add_case = QPushButton(t("openfoam.add_case"))
    run = QPushButton(t("openfoam.validate"))
    for control in (add_file, add_case, run):
        actions.addWidget(control)
    layout.addWidget(status)
    layout.addLayout(actions)
    layout.addWidget(paths)
    layout.addWidget(output)

    def add_paths(selected):
        existing = {paths.item(index).text() for index in range(paths.count())}
        for item in selected:
            value = str(item)
            if value not in existing:
                paths.addItem(value)
                existing.add(value)

    def choose_files():
        selected, _filter = QFileDialog.getOpenFileNames(
            widget, t("openfoam.add_file"), "", t("openfoam.dictionary_filter")
        )
        add_paths(selected)

    def choose_case():
        selected = QFileDialog.getExistingDirectory(widget, t("openfoam.add_case"))
        if selected:
            add_paths([selected])

    def validate():
        selected = [Path(paths.item(index).text()) for index in range(paths.count())]
        if not selected:
            status.setText(t("openfoam.select_path"))
            return
        try:
            result = lint_paths(selected)
        except Exception as exc:
            status.setText(t("openfoam.lint_failed").format(error=exc))
            return
        output.setPlainText(result.to_markdown())
        status.setText(t("openfoam.lint_summary").format(
            files=len(result.files_checked), errors=result.errors, warnings=result.warnings
        ))

    add_file.clicked.connect(choose_files)
    add_case.clicked.connect(choose_case)
    run.clicked.connect(validate)
    if initial_paths:
        validate()
    return widget
