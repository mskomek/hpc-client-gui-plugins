"""Reciprocal compatibility contract.

The main application guarantees that a registry lookup only ever selects
versions whose ``requires_app`` range admits the running release. This test
is the registry-side mirror. It intentionally avoids importing application
code so the plugin repository stays independently validatable, and it
enforces the schema capability floors through ``scripts/schema_compatibility``.

Supported consumers:
- the oldest supported application line must always have at least one
  compatible version of every plugin id (fallback resolution);
- newer plugin versions may require newer application releases, but never a
  release older than the first one implementing their payload schema.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from packaging.specifiers import SpecifierSet
from packaging.version import Version

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from schema_compatibility import (  # noqa: E402
    MIN_APP_VERSION_FOR_SCHEMA,
    schema_floor_error,
)

# Oldest application line the registry still serves (published v1.5.5 build).
CURRENT_APP_VERSION = Version("1.5.5")
# Published v1.5.8 accepts cluster-profile schemas 1-2 only.
RELEASED_APP_VERSION = Version("1.5.8")
# First application release with schema 3/4 support (current develop line).
SCHEMA_V3_APP_VERSION = Version("1.5.9")

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


def _entries_by_id(registry: dict) -> dict[str, list[dict]]:
    by_id: dict[str, list[dict]] = {}
    for entry in registry["plugins"]:
        by_id.setdefault(entry["id"], []).append(entry)
    return by_id


def _latest_compatible(entries: list[dict], app_version: Version) -> dict | None:
    candidates = [
        entry
        for entry in entries
        if _range_admits(str(entry["requires_app"]), app_version)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda entry: Version(entry["version"]))


def test_registry_protocol_and_entry_api_versions(registry: dict):
    assert registry["plugin_api"] == 1
    for entry in registry["plugins"]:
        assert entry["plugin_api"] == 1
        assert "linter-tool" not in entry.get("capabilities", [])


def test_every_plugin_has_a_version_for_the_oldest_supported_app_line(registry: dict):
    problems = []
    for plugin_id, entries in _entries_by_id(registry).items():
        if _latest_compatible(entries, CURRENT_APP_VERSION) is None:
            problems.append(f"{plugin_id} has no version compatible with {CURRENT_APP_VERSION}")
    assert not problems, "\n".join(problems)


def test_released_app_gets_latest_genuinely_compatible_truba(registry: dict):
    """The v1.5.8 release supports schemas 1-2, so TRUBA 1.4.0/1.5.0 must
    not be offered; the newest compatible version is 1.3.0."""
    by_id = _entries_by_id(registry)
    truba_108 = _latest_compatible(by_id["org.hpcclient.truba"], RELEASED_APP_VERSION)
    assert truba_108 is not None
    assert truba_108["version"] == "1.3.0"
    assert truba_108["requires_app"] == ">=1.5.5"

    excluded = {
        entry["version"]
        for entry in by_id["org.hpcclient.truba"]
        if not _range_admits(str(entry["requires_app"]), RELEASED_APP_VERSION)
    }
    assert {"1.4.0", "1.5.0"} <= excluded


def test_schema_capable_app_resolves_newest_truba(registry: dict):
    """The first schema-3/4 capable release can install 1.4.0 and 1.5.0."""
    by_id = _entries_by_id(registry)
    latest = _latest_compatible(by_id["org.hpcclient.truba"], SCHEMA_V3_APP_VERSION)
    assert latest is not None
    assert latest["version"] == "1.5.0"
    for version in ("1.4.0", "1.5.0"):
        entry = next(e for e in by_id["org.hpcclient.truba"] if e["version"] == version)
        assert _range_admits(str(entry["requires_app"]), SCHEMA_V3_APP_VERSION)


def test_fluent_stays_available_on_every_supported_line(registry: dict):
    by_id = _entries_by_id(registry)
    for app_version in (CURRENT_APP_VERSION, RELEASED_APP_VERSION, SCHEMA_V3_APP_VERSION):
        assert _latest_compatible(by_id["org.hpcclient.fluent"], app_version) is not None


def test_cluster_profile_schema_floors_are_honest(registry: dict):
    """No published cluster-profile payload may claim an app release that
    predates support for its own schema version."""
    problems = []
    for entry in registry["plugins"]:
        manifest_path = REPO_ROOT / entry["manifest_path"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for file_entry in manifest.get("files", []):
            if file_entry.get("role") != "cluster-profile":
                continue
            payload_path = manifest_path.parent / file_entry["path"]
            profile = json.loads(payload_path.read_text(encoding="utf-8"))
            error = schema_floor_error(
                profile.get("schema_version"), str(manifest.get("requires_app", ""))
            )
            if error:
                problems.append(f"{entry['id']}@{entry['version']}: {error}")
    assert not problems, "\n".join(problems)


def test_schema_minimum_versions_are_release_facts():
    assert MIN_APP_VERSION_FOR_SCHEMA == {1: "1.4.0", 2: "1.5.5", 3: "1.5.9", 4: "1.5.9"}


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


def test_future_schema_is_not_published(registry: dict):
    """No published payload may declare a schema newer than the matrix."""
    for entry in registry["plugins"]:
        manifest_path = REPO_ROOT / entry["manifest_path"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for file_entry in manifest.get("files", []):
            if file_entry.get("role") != "cluster-profile":
                continue
            profile = json.loads(
                (manifest_path.parent / file_entry["path"]).read_text(encoding="utf-8")
            )
            assert profile["schema_version"] in MIN_APP_VERSION_FOR_SCHEMA
