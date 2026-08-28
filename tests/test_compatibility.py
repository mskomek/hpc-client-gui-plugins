"""Reciprocal compatibility contract.

The main application guarantees that ``find_registry_entry`` only ever
selects versions whose ``requires_app`` range admits the running release.
This test is the registry-side mirror: it verifies with PEP 440 tooling
(``packaging``) that every published entry targets its declared Plugin
API generation correctly:

- Plugin API v1 entries stay installable by the 1.4.x application line;
- Plugin API v2 entries (capability 'linter-tool') require application
  >= 1.5.0, the first release that understands them, so older clients
  never select a package they cannot load.

It intentionally avoids importing application code so the plugin
repository stays independently validatable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

REPO_ROOT = Path(__file__).resolve().parent.parent
CURRENT_APP_VERSION = Version("1.4.0")
V2_APP_FLOOR = Version("1.5.3")

# Operators supported by Plugin API v1 (see docs/PLUGIN_API_V1.md).
SUPPORTED_OPERATORS = {">=", "<=", "==", "~="}


@pytest.fixture(scope="module")
def registry() -> dict:
    return json.loads((REPO_ROOT / "registry.json").read_text(encoding="utf-8"))


def _range_admits(requires_app: str, version: Version) -> bool:
    specifier = SpecifierSet(requires_app)
    for clause in specifier:
        if clause.operator not in SUPPORTED_OPERATORS:
            return False
    return version in specifier


def test_registry_protocol_and_entry_api_versions(registry: dict):
    assert registry["plugin_api"] == 1
    for entry in registry["plugins"]:
        if entry["plugin_api"] == 1:
            assert "linter-tool" not in entry.get("capabilities", [])
        else:
            assert entry["plugin_api"] == 2
            assert "linter-tool" in entry.get("capabilities", []), (
                f"{entry['id']}@{entry['version']}: Plugin API v2 entries must "
                "declare the linter-tool capability"
            )


def test_all_published_versions_installable_on_target_app_lines(registry: dict):
    problems = []
    for entry in registry["plugins"]:
        try:
            ok_v1_line = _range_admits(str(entry["requires_app"]), CURRENT_APP_VERSION)
            ok_v2_line = _range_admits(str(entry["requires_app"]), V2_APP_FLOOR)
        except InvalidSpecifier:
            ok_v1_line = ok_v2_line = False
        if entry["plugin_api"] == 1:
            if not ok_v1_line:
                problems.append(
                    f"{entry['id']}@{entry['version']} requires_app="
                    f"'{entry['requires_app']}' excludes {CURRENT_APP_VERSION}"
                )
        else:
            if not ok_v2_line:
                problems.append(
                    f"{entry['id']}@{entry['version']} requires_app="
                    f"'{entry['requires_app']}' excludes {V2_APP_FLOOR}"
                )
            if ok_v1_line:
                problems.append(
                    f"{entry['id']}@{entry['version']} is Plugin API v2 but "
                    f"would be selected by old clients on {CURRENT_APP_VERSION}"
                )
    assert not problems, "\n".join(problems)


def _requirement_floor(entry: dict) -> Version:
    """Extract the lowest version mentioned in requires_app."""
    text = str(entry["requires_app"]).split(",")[0].strip()
    return Version(text.lstrip("><=~").strip())


def test_no_version_shadowing_across_compatibility(registry: dict):
    """For each id, newer plugin versions must not declare lower app
    requirements, so 'latest compatible' resolution stays monotonic."""
    by_id: dict[str, list[dict]] = {}
    for entry in registry["plugins"]:
        by_id.setdefault(entry["id"], []).append(entry)
    for plugin_id, entries in by_id.items():
        entries_sorted = sorted(entries, key=lambda e: Version(e["version"]))
        floors = [_requirement_floor(e) for e in entries_sorted]
        assert floors == sorted(floors), (
            f"{plugin_id}: newer versions must not declare lower requirements"
        )
