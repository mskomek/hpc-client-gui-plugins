"""Published-plugin immutability and registry compatibility override.

Once a plugin version is published its manifest and declared payload bytes
are frozen. A compatibility mistake is corrected at the registry level; new
content requires a new plugin version. These tests run the real validator
against a throwaway copy of the repository, so they exercise the shipped
gate rather than a reimplementation of it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import published_lock  # noqa: E402
import validate_registry  # noqa: E402

FROZEN_ID = "org.hpcclient.truba"
FROZEN_VERSION = "1.4.0"
FROZEN_DIR = f"plugins/truba/{FROZEN_VERSION}"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """An isolated copy of the repository the validator can be run against."""
    target = tmp_path / "registry"
    shutil.copytree(
        REPO_ROOT,
        target,
        ignore=shutil.ignore_patterns(
            ".git", ".github", "__pycache__", "*.pyc", ".pytest_cache", ".venv"
        ),
    )
    return target


def _validate(repo: Path) -> list[str]:
    errors, _warnings = validate_registry.validate_repository(repo)
    return errors


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rehash(repo: Path, plugin_dir: str, plugin_id: str, version: str) -> None:
    """Do exactly what a naive 'fix the hashes' pass would do."""
    manifest_path = repo / plugin_dir / "manifest.json"
    manifest = _load(manifest_path)
    for declared in manifest["files"]:
        payload = manifest_path.parent / declared["path"]
        declared["sha256"] = _sha256(payload)
        declared["size"] = payload.stat().st_size
    _dump(manifest_path, manifest)

    registry_path = repo / "registry.json"
    registry = _load(registry_path)
    for entry in registry["plugins"]:
        if entry["id"] == plugin_id and entry["version"] == version:
            entry["manifest_sha256"] = _sha256(manifest_path)
    _dump(registry_path, registry)


def _entry(registry: dict, plugin_id: str, version: str) -> dict:
    return next(
        item
        for item in registry["plugins"]
        if item["id"] == plugin_id and item["version"] == version
    )


def _immutability_failures(errors: list[str]) -> list[str]:
    return [error for error in errors if "is immutable" in error]


# A. unchanged historical package -> PASS
def test_unchanged_repository_passes(repo: Path):
    assert _validate(repo) == []


# B. published manifest changed -> FAIL
def test_published_manifest_change_fails(repo: Path):
    manifest_path = repo / FROZEN_DIR / "manifest.json"
    manifest = _load(manifest_path)
    manifest["description"] = manifest["description"] + " (edited)"
    _dump(manifest_path, manifest)
    registry = _load(repo / "registry.json")
    _entry(registry, FROZEN_ID, FROZEN_VERSION)["manifest_sha256"] = _sha256(
        manifest_path
    )
    _dump(repo / "registry.json", registry)

    assert _immutability_failures(_validate(repo))


# C. payload changed -> FAIL
def test_published_payload_change_fails(repo: Path):
    profile_path = repo / FROZEN_DIR / "cluster-profile.json"
    profile = _load(profile_path)
    profile["description"] = "mutated after publication"
    _dump(profile_path, profile)
    _rehash(repo, FROZEN_DIR, FROZEN_ID, FROZEN_VERSION)

    assert _immutability_failures(_validate(repo))


# D. declared package documentation changed -> FAIL
def test_published_documentation_change_fails(repo: Path):
    readme = repo / FROZEN_DIR / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8") + "\nAdded after publication.\n",
        encoding="utf-8",
        newline="\n",
    )
    _rehash(repo, FROZEN_DIR, FROZEN_ID, FROZEN_VERSION)

    assert _immutability_failures(_validate(repo))


# E. entirely new plugin version -> PASS
def test_new_plugin_version_passes(repo: Path):
    source = repo / FROZEN_DIR
    new_version = "1.4.1"
    target = repo / "plugins/truba" / new_version
    shutil.copytree(source, target)

    manifest_path = target / "manifest.json"
    manifest = _load(manifest_path)
    manifest["version"] = new_version
    _dump(manifest_path, manifest)

    registry_path = repo / "registry.json"
    registry = _load(registry_path)
    published = _entry(registry, FROZEN_ID, FROZEN_VERSION)
    new_entry = dict(published)
    new_entry["version"] = new_version
    new_entry["manifest_path"] = f"plugins/truba/{new_version}/manifest.json"
    new_entry["manifest_sha256"] = _sha256(manifest_path)
    registry["plugins"].insert(registry["plugins"].index(published), new_entry)
    _dump(registry_path, registry)

    assert _validate(repo) == []


# F. registry-only compatibility override, package bytes unchanged -> PASS
def test_registry_only_compatibility_override_passes(repo: Path):
    registry_path = repo / "registry.json"
    registry = _load(registry_path)
    entry = _entry(registry, FROZEN_ID, FROZEN_VERSION)
    entry["compatibility_override"] = {
        "requires_app": ">=1.6.0",
        "reason": "test: narrow compatibility without touching package bytes",
        "recorded": "2026-09-15",
    }
    _dump(registry_path, registry)

    assert _validate(repo) == []


def test_compatibility_override_may_not_widen_compatibility(repo: Path):
    registry_path = repo / "registry.json"
    registry = _load(registry_path)
    entry = _entry(registry, FROZEN_ID, FROZEN_VERSION)
    entry["compatibility_override"] = {
        "requires_app": ">=1.5.5",
        "reason": "test: illegally widen an immutable floor",
        "recorded": "2026-09-15",
    }
    _dump(registry_path, registry)

    errors = _validate(repo)
    assert any("may only narrow compatibility" in error for error in errors), errors


def test_compatibility_override_cannot_defeat_the_schema_floor(repo: Path):
    """An override is still checked against the schema capability matrix."""
    from schema_compatibility import effective_requires_app, schema_floor_error

    entry = {
        "requires_app": ">=1.5.9",
        "compatibility_override": {"requires_app": ">=1.5.9", "reason": "x"},
    }
    assert effective_requires_app(entry) == ">=1.5.9"
    assert schema_floor_error(3, effective_requires_app(entry)) is None
    assert schema_floor_error(3, ">=1.5.8") is not None


# G. package mutated + hashes regenerated -> FAIL
def test_rehashing_cannot_bless_a_mutation(repo: Path):
    profile_path = repo / FROZEN_DIR / "cluster-profile.json"
    profile = _load(profile_path)
    profile["name"] = "TRUBA (rehashed)"
    _dump(profile_path, profile)
    _rehash(repo, FROZEN_DIR, FROZEN_ID, FROZEN_VERSION)

    errors = _validate(repo)
    # Integrity checks are satisfied by the regenerated hashes ...
    assert not [error for error in errors if "sha256 mismatch" in error]
    # ... and the immutability ledger still fails the change closed.
    failures = _immutability_failures(errors)
    assert failures
    assert "Create a new plugin version" in failures[0]


def test_every_registry_entry_published_on_main_is_frozen():
    """The ledger must not silently lose a package it already froze."""
    lock = published_lock.load_lock(REPO_ROOT)
    for key in (
        "org.hpcclient.truba@1.3.0",
        "org.hpcclient.truba@1.4.0",
        "org.hpcclient.truba@1.5.0",
        "org.hpcclient.fluent@0.3.0",
    ):
        assert key in lock["published"], f"{key} lost its immutability record"


def test_recording_an_already_published_version_is_refused(repo: Path, capsys):
    assert published_lock.record(f"{FROZEN_ID}@{FROZEN_VERSION}", root=repo) == 1
    assert "already published and frozen" in capsys.readouterr().err
