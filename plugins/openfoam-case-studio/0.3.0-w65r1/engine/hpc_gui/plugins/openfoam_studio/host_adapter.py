"""Proposed host contribution metadata for the OpenFOAM plugins (W65 HOST-002).

This module is not registered with the current host loader: the returned
shape is descriptive data, not a live file-context or Plugins-menu binding.
The manifest and host action dispatch still need an integration change.
"""

from __future__ import annotations

FILE_CONTEXT_ACTIONS = (
    {"id": "of.newCase", "label_en": "New OpenFOAM Case", "label_tr": "Yeni OpenFOAM Vakası"},
    {"id": "of.openStudio", "label_en": "Open with OpenFOAM Case Studio",
     "label_tr": "OpenFOAM Vaka Stüdyosu ile Aç"},
    {"id": "of.validate", "label_en": "Validate with OpenFOAM Linter",
     "label_tr": "OpenFOAM Denetleyici ile Doğrula"},
    {"id": "of.createJob", "label_en": "Create Job Draft", "label_tr": "İş Taslağı Oluştur"},
)

PLUGIN_MENU = (
    {"id": "of.studio", "plugin": "openfoam-case-studio", "version": "0.3.0-w65r1"},
    {"id": "of.linter", "plugin": "openfoam-linter", "version": "0.2.0-w65r1"},
)


def contributions() -> dict:
    return {"file_context": list(FILE_CONTEXT_ACTIONS), "plugin_menu": list(PLUGIN_MENU),
            "requires_app": ">=1.5.9", "sftp mirrored": True}
