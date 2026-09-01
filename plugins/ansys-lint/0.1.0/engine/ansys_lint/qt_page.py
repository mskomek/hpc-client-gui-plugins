"""PySide6 GUI page for the ANSYS Script & Journal Linter.

This module is imported lazily by the host application's plugin tool
host - the engine itself never requires Qt. All long work runs on a
``QThreadPool`` worker so the GUI stays responsive.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .cli import render_text
from .dialects import DIALECT_LABELS
from .model import ExecMode, LintOptions, Severity, Strictness, TargetOS
from .api import lint_paths


class _WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class _LintWorker(QRunnable):
    def __init__(self, paths: list[str], options: LintOptions) -> None:
        super().__init__()
        self.paths = paths
        self.options = options
        self.signals = _WorkerSignals()

    def run(self) -> None:  # pragma: no cover - Qt thread plumbing
        try:
            result = lint_paths(self.paths, self.options)
            self.signals.finished.emit(result)
        except Exception as exc:  # defensive: never crash the pool thread
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")


def build_page(parent=None, initial_paths=None) -> QWidget:
    page = QWidget(parent)
    if initial_paths is None:
        initial_paths = []

    layout = QHBoxLayout(page)

    # ---- Left column: inputs -------------------------------------------------
    left = QVBoxLayout()

    files_group = QGroupBox("Files")
    files_layout = QVBoxLayout(files_group)
    from PySide6.QtWidgets import QListWidget

    path_list = QListWidget()
    for item in initial_paths:
        path_list.addItem(str(item))
    files_layout.addWidget(path_list)

    file_buttons = QHBoxLayout()
    btn_add_files = QPushButton("Add files…")
    btn_add_folder = QPushButton("Add folder…")
    btn_remove = QPushButton("Remove selected")
    file_buttons.addWidget(btn_add_files)
    file_buttons.addWidget(btn_add_folder)
    file_buttons.addWidget(btn_remove)
    files_layout.addLayout(file_buttons)
    left.addWidget(files_group)

    settings_group = QGroupBox("Lint settings")
    grid = QGridLayout(settings_group)

    dialect_combo = QComboBox()
    dialect_combo.addItem("Auto-detect", None)
    for key in sorted(DIALECT_LABELS):
        dialect_combo.addItem(DIALECT_LABELS[key], key)
    version_combo = QComboBox()
    for version in ("24.2", "25.1", "25.2", "26.1"):
        version_combo.addItem(version)
    version_combo.setCurrentText("25.2")
    mode_combo = QComboBox()
    mode_combo.addItem("batch", ExecMode.BATCH)
    mode_combo.addItem("headless", ExecMode.HEADLESS)
    mode_combo.addItem("interactive", ExecMode.INTERACTIVE)
    os_combo = QComboBox()
    os_combo.addItem("Linux (TRUBA/HPC)", TargetOS.LINUX)
    os_combo.addItem("Windows", TargetOS.WINDOWS)
    strict_combo = QComboBox()
    strict_combo.addItem("lenient", Strictness.LENIENT)
    strict_combo.addItem("strict", Strictness.STRICT)
    launch_edit = QLineEdit()
    launch_edit.setPlaceholderText('e.g. fluent 3ddp -g -i job.jou or runwb2 -B -R job.wbjn')

    rows = [
        ("Dialect override", dialect_combo),
        ("Ansys version", version_combo),
        ("Execution mode", mode_combo),
        ("Target OS", os_combo),
        ("Strictness", strict_combo),
        ("Launch command", launch_edit),
    ]
    for row, (label, widget) in enumerate(rows):
        grid.addWidget(QLabel(label), row, 0)
        grid.addWidget(widget, row, 1)
    left.addWidget(settings_group)

    run_button = QPushButton("Run linter")
    run_button.setDefault(True)
    left.addWidget(run_button)
    left.addStretch(1)

    layout.addLayout(left, 0)

    # ---- Right column: results ----------------------------------------------
    right = QVBoxLayout()

    filters = QHBoxLayout()
    filter_errors = QCheckBox("Errors")
    filter_errors.setChecked(True)
    filter_warnings = QCheckBox("Warnings")
    filter_warnings.setChecked(True)
    filter_infos = QCheckBox("Info")
    filter_infos.setChecked(True)
    for box in (filter_errors, filter_warnings, filter_infos):
        filters.addWidget(box)
    filters.addStretch(1)
    right.addLayout(filters)

    tree = QTreeWidget()
    tree.setColumnCount(4)
    tree.setHeaderLabels(["File / finding", "", "Code", "Severity"])
    tree.header().resizeSection(0, 420)
    tree.setAlternatingRowColors(True)
    right.addWidget(tree, 1)

    bottom = QHBoxLayout()
    summary_label = QLabel("No results yet.")
    bottom.addWidget(summary_label, 1)
    btn_copy = QPushButton("Copy diagnostic")
    btn_export_json = QPushButton("Export JSON…")
    btn_export_txt = QPushButton("Export text…")
    open_link_btn = QPushButton("Open documentation link")
    bottom.addWidget(open_link_btn)
    bottom.addWidget(btn_copy)
    bottom.addWidget(btn_export_json)
    bottom.addWidget(btn_export_txt)
    right.addLayout(bottom)

    layout.addLayout(right, 1)

    state = {"last_result": None}

    def _collect_options() -> LintOptions:
        return LintOptions(
            target_version=version_combo.currentText(),
            exec_mode=ExecMode(mode_combo.currentData()),
            target_os=TargetOS(os_combo.currentData()),
            strictness=Strictness(strict_combo.currentText()),
            dialect_override=dialect_combo.currentData(),
            launch_command=launch_edit.text().strip(),
        )

    def _refresh_filters() -> None:
        allowed = {
            Severity.ERROR: filter_errors.isChecked(),
            Severity.WARNING: filter_warnings.isChecked(),
            Severity.INFO: filter_infos.isChecked(),
        }
        for index in range(tree.topLevelItemCount()):
            file_item = tree.topLevelItem(index)
            visible_children = 0
            for child_index in range(file_item.childCount()):
                child = file_item.child(child_index)
                severity = child.data(0, Qt.UserRole)
                visible = allowed.get(severity, True)
                child.setHidden(not visible)
                if visible:
                    visible_children += 1
            file_item.setHidden(visible_children == 0 and file_item.childCount() > 0)

    filter_errors.stateChanged.connect(lambda _: _refresh_filters())
    filter_warnings.stateChanged.connect(lambda _: _refresh_filters())
    filter_infos.stateChanged.connect(lambda _: _refresh_filters())

    def _populate(result) -> None:
        tree.clear()
        totals = {"error": 0, "warning": 0, "info": 0}
        for file_result in sorted(result.files, key=lambda f: f.file_path):
            detection = file_result.detection
            header_parts = [file_result.file_path]
            meta_bits = []
            if detection.product != "unknown":
                meta_bits.append(detection.product)
            if detection.detected_version:
                meta_bits.append(f"v{detection.detected_version}")
            meta_bits.append(f"confidence {detection.confidence:.2f}")
            file_item = QTreeWidgetItem(
                [header_parts[0], ", ".join(meta_bits), "", ""]
            )
            tree.addTopLevelItem(file_item)
            for diag in file_result.sorted_diagnostics():
                location = "?" if diag.line is None else f"{diag.line}:{diag.column or 1}"
                child = QTreeWidgetItem(
                    [
                        f"[{location}] {diag.message}",
                        diag.source_url or "",
                        diag.code,
                        diag.severity.value,
                    ]
                )
                tooltip_lines = [diag.explanation or diag.message]
                if diag.suggested_fix:
                    tooltip_lines.append(f"Suggested fix: {diag.suggested_fix}")
                if diag.source_url:
                    tooltip_lines.append(f"Source: {diag.source_title} ({diag.source_url})")
                if diag.is_heuristic:
                    tooltip_lines.append("(heuristic recommendation - verify manually)")
                child.setToolTip(0, "\n".join(tooltip_lines))
                child.setData(0, Qt.UserRole, diag.severity)
                child.setIcon(0, _severity_icon(diag.severity))
                file_item.addChild(child)
            for key in totals:
                totals[key] += file_result.summary[key]
        summary_label.setText(
            f"{totals['error']} error(s), {totals['warning']} warning(s), {totals['info']} info"
        )
        _refresh_filters()

    def _on_finished(result) -> None:
        run_button.setEnabled(True)
        state["last_result"] = result
        _populate(result)

    def _on_failed(message: str) -> None:
        run_button.setEnabled(True)
        QMessageBox.critical(page, "Linter failure", message)

    def _run() -> None:
        paths = [
            path_list.item(i).text()
            for i in range(path_list.count())
        ]
        if not paths:
            QMessageBox.information(page, "No input", "Add at least one file or folder first.")
            return
        run_button.setEnabled(False)
        worker = _LintWorker(paths, _collect_options())
        worker.signals.finished.connect(_on_finished)
        worker.signals.failed.connect(_on_failed)
        QThreadPool.globalInstance().start(worker)

    def _add_files() -> None:
        files, _filter = QFileDialog.getOpenFileNames(page, "Select script/journal files")
        for name in files:
            path_list.addItem(name)

    def _add_folder() -> None:
        folder = QFileDialog.getExistingDirectory(page, "Select folder to scan")
        if folder:
            path_list.addItem(folder)

    def _remove_selected() -> None:
        for item in path_list.selectedItems():
            path_list.takeItem(path_list.row(item))

    def _current_diagnostic():
        item = tree.currentItem()
        if item is None or item.parent() is None:
            return None
        file_item = item.parent()
        file_path = file_item.text(0)
        location = item.text(0)
        code = item.text(2)
        result = state["last_result"]
        if not result:
            return None
        for file_result in result.files:
            if file_result.file_path != file_path:
                continue
            for diag in file_result.diagnostics:
                loc = "?" if diag.line is None else f"{diag.line}:{diag.column or 1}"
                if f"[{loc}] {diag.message}" == location and diag.code == code:
                    return diag
        return None

    def _copy() -> None:
        diag = _current_diagnostic()
        if diag is None:
            return
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        clipboard.setText(
            f"{diag.code} [{diag.severity.value}] "
            f"{diag.file_path}:{diag.line}:{diag.column or 1}\n{diag.message}\n"
            f"{diag.explanation}\nFix: {diag.suggested_fix}"
        )

    def _export_json() -> None:
        result = state["last_result"]
        if not result:
            return
        path, _filter = QFileDialog.getSaveFileName(
            page, "Export diagnostics as JSON", "ansys-lint-report.json", "JSON (*.json)"
        )
        if not path:
            return
        payload = {
            "tool": "ansys-journal-lint",
            "files": [
                {
                    "path": fr.file_path,
                    "detection": fr.detection.to_dict(),
                    "summary": fr.summary,
                    "diagnostics": [d.to_dict() for d in fr.sorted_diagnostics()],
                }
                for fr in result.files
            ],
            "summary": result.summary,
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)

    def _export_txt() -> None:
        result = state["last_result"]
        if not result:
            return
        path, _filter = QFileDialog.getSaveFileName(
            page, "Export diagnostics as text", "ansys-lint-report.txt", "Text (*.txt)"
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(render_text(result))

    def _open_link() -> None:
        diag = _current_diagnostic()
        if diag is None or not diag.source_url:
            QMessageBox.information(
                page, "No source link", "The selected diagnostic has no official documentation link."
            )
            return
        QDesktopServices.openUrl(QUrl(diag.source_url))

    run_button.clicked.connect(_run)
    btn_add_files.clicked.connect(_add_files)
    btn_add_folder.clicked.connect(_add_folder)
    btn_remove.clicked.connect(_remove_selected)
    btn_copy.clicked.connect(_copy)
    btn_export_json.clicked.connect(_export_json)
    btn_export_txt.clicked.connect(_export_txt)
    open_link_btn.clicked.connect(_open_link)

    return page


def _severity_icon(severity: Severity):
    from PySide6.QtGui import QIcon, QPixmap, QColor

    pixmap = QPixmap(12, 12)
    color = {"error": "#c0392b", "warning": "#e67e22", "info": "#2980b9"}[severity.value]
    pixmap.fill(QColor(color))
    return QIcon(pixmap)
