from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from host_rendered_tools import provides_host_rendered_tool  # noqa: E402
from validate_registry import validate_entrypoint_files  # noqa: E402


def _manifest(actions: list[str], capabilities=("application-tools",)) -> dict:
    items = [{"kind": "action", "id": f"a{i}", "label": "x", "action": a} for i, a in enumerate(actions)]
    return {
        "plugin_api": 1,
        "capabilities": list(capabilities),
        "entrypoints": {},
        "files": [],
        "ui_contributions": {"plugins_menu": {"label": "x", "items": items}},
    }


def _errors(manifest: dict) -> list[str]:
    errors: list[str] = []
    validate_entrypoint_files(manifest, ROOT, "test", errors)
    return errors


def test_application_tools_satisfied_by_host_rendered_action():
    assert provides_host_rendered_tool(_manifest(["journal_studio.open"]))
    assert _errors(_manifest(["journal_studio.open"])) == []


def test_application_tools_without_action_or_entrypoint_rejected():
    errors = _errors(_manifest(["editor.lint_current"]))
    assert any("capability 'application-tools' is declared" in e for e in errors)
    assert _errors(_manifest([])) != []


def test_host_rendered_action_does_not_satisfy_other_capabilities():
    errors = _errors(_manifest(["journal_studio.open"], capabilities=("lint-rules",)))
    assert any("capability 'lint-rules' is declared" in e for e in errors)


def test_published_journal_studio_manifest_passes():
    manifest_path = ROOT / "plugins" / "ansys-journal-studio" / "0.1.0" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert _errors(manifest) == []
