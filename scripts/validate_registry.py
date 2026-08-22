#!/usr/bin/env python3
"""Validate the official HPC Client GUI plugin registry.

Checks, in order:
1. registry.json loads and validates against schema/registry.schema.json;
2. plugin IDs and (id, version) pairs are unique;
3. each referenced manifest exists locally and its SHA-256 matches;
4. each manifest validates against schema/manifest.schema.json;
5. manifest id/version match the registry entry;
6. every declared file exists with the declared size and SHA-256;
7. payloads are declarative data (no executable-looking files);
8. capability-specific entrypoint payloads validate against their schemas.

Exit status is non-zero on any error.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

try:
    from jsonschema import Draft7Validator
    from packaging.specifiers import InvalidSpecifier, SpecifierSet
    from packaging.version import InvalidVersion, Version
except ImportError:  # pragma: no cover
    print("Missing dependencies. Run: pip install jsonschema packaging", file=sys.stderr)
    raise SystemExit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schema"

ALLOWED_PAYLOAD_EXTENSIONS = {".json", ".md", ".txt"}

SCHEMA_FOR_ROLE = {
    "cluster-profile": "cluster-profile.schema.json",
    "lint-index": "lint-index.schema.json",
    "lint-rules": "lint-rule.schema.json",
    "template-index": "template-index.schema.json",
    "template-content": "template.schema.json",
}

CAPABILITY_ENTRYPOINT_KEY = {
    "cluster-profile": "cluster_profiles",
    "lint-rules": "lint_index",
    "job-template": "template_index",
    "application-tools": "template_index",
}

ENTRYPOINT_ROLES = {
    "cluster_profiles": ("cluster-profile",),
    "lint_index": ("lint-index",),
    "template_index": ("template-index",),
}


class ValidationFailed(Exception):
    """Raised when the registry has at least one fatal problem."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_against_schema(instance, schema_path: Path, label: str, errors: list[str]) -> None:
    schema = load_json(schema_path)
    validator = Draft7Validator(schema)
    for issue in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        location = "/".join(str(part) for part in issue.absolute_path) or "<root>"
        errors.append(f"{label}: schema violation at '{location}': {issue.message}")


def check_relative_path(path: str, label: str, errors: list[str]) -> None:
    """Reject unsafe paths before any filesystem access."""
    if not path or not isinstance(path, str):
        errors.append(f"{label}: path must be a non-empty string")
        return
    if "\\" in path:
        errors.append(f"{label}: backslash is not allowed in paths ('{path}')")
        return
    if path.startswith("/"):
        errors.append(f"{label}: absolute POSIX path ('{path}')")
        return
    if re.match(r"^[A-Za-z]:", path):
        errors.append(f"{label}: Windows drive-style path ('{path}')")
        return
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", path):
        errors.append(f"{label}: URL is not a valid file path ('{path}')")
        return
    segments = path.split("/")
    if any(segment == ".." for segment in segments):
        errors.append(f"{label}: '..' segment is not allowed ('{path}')")
    if any(segment == "" for segment in segments[:-1]) or segments[-1] == "":
        errors.append(f"{label}: empty path segment ('{path}')")


def check_requires_app(value: str, label: str, errors: list[str]) -> None:
    try:
        specifier = SpecifierSet(value)
    except InvalidSpecifier:
        errors.append(f"{label}: requires_app '{value}' is not a supported version range")
        return
    # The app supports a small subset: bare versions plus >=, <=, ==, ~=.
    for clause in specifier:
        if clause.operator not in {">=", "<=", "==", "~="}:
            errors.append(
                f"{label}: requires_app operator '{clause.operator}' is not supported by Plugin API v1"
            )


def check_semver(value: str, label: str, errors: list[str]) -> None:
    try:
        Version(value)
    except InvalidVersion:
        errors.append(f"{label}: version '{value}' is not a valid semantic version")


def validate_payload_role(role: str, path: Path, label: str, errors: list[str]) -> None:
    schema_name = SCHEMA_FOR_ROLE.get(role)
    if schema_name is None:
        return
    try:
        instance = load_json(path)
    except json.JSONDecodeError as exc:
        errors.append(f"{label}: payload is not valid JSON ({exc})")
        return
    validate_against_schema(instance, SCHEMA_DIR / schema_name, f"{label} [{role}]", errors)


def validate_entrypoint_files(manifest: dict, manifest_dir: Path, label: str, errors: list[str]) -> None:
    capabilities = set(manifest.get("capabilities", []))
    entrypoints = manifest.get("entrypoints", {})
    declared_files = {entry["path"]: entry for entry in manifest.get("files", [])}

    for capability in sorted(capabilities):
        key = CAPABILITY_ENTRYPOINT_KEY.get(capability)
        if key is None:
            continue
        expected_roles = ENTRYPOINT_ROLES[key]
        raw_entries = entrypoints.get(key)
        if raw_entries is None:
            continue
        if isinstance(raw_entries, str):
            raw_entries = [raw_entries]
        for entry_rel in raw_entries:
            entry_label = f"{label}: entrypoint '{key}' -> '{entry_rel}'"
            errors_before = len(errors)
            check_relative_path(entry_rel, entry_label, errors)
            if len(errors) > errors_before:
                continue
            file_entry = declared_files.get(entry_rel)
            if file_entry is None:
                errors.append(f"{entry_label}: not declared in manifest.files")
                continue
            if file_entry.get("role") not in expected_roles:
                errors.append(
                    f"{entry_label}: role '{file_entry.get('role')}' does not match expected {expected_roles}"
                )
                continue
            payload_path = manifest_dir / entry_rel
            if payload_path.is_file():
                validate_payload_role(file_entry["role"], payload_path, entry_label, errors)


def collect_executable_payload_errors(files: list[dict], label: str, errors: list[str]) -> None:
    for entry in files:
        suffix = Path(entry["path"]).suffix.lower()
        if suffix not in ALLOWED_PAYLOAD_EXTENSIONS:
            errors.append(
                f"{label}: payload '{entry['path']}' has executable-looking extension "
                f"'{suffix or '<none>'}'; Plugin API v1 allows only "
                f"{sorted(ALLOWED_PAYLOAD_EXTENSIONS)}"
            )


def validate_plugin_entry(entry: dict, seen_ids: dict, errors: list[str], warnings: list[str]) -> None:
    plugin_id = entry["id"]
    version = entry["version"]
    label = f"plugin {plugin_id}@{version}"

    previous = seen_ids.setdefault(plugin_id, set())
    if version in previous:
        errors.append(f"duplicate registry entry for {label}")
    previous.add(version)

    check_semver(version, label, errors)
    check_requires_app(entry["requires_app"], label, errors)

    manifest_rel = entry["manifest_path"]
    errors_before = len(errors)
    check_relative_path(manifest_rel, f"{label}: manifest_path", errors)
    if len(errors) > errors_before:
        return

    manifest_path = REPO_ROOT / manifest_rel
    if not manifest_path.is_file():
        errors.append(f"{label}: manifest not found at '{manifest_rel}'")
        return

    actual_manifest_hash = sha256_of(manifest_path)
    if actual_manifest_hash != entry["manifest_sha256"]:
        errors.append(
            f"{label}: manifest SHA-256 mismatch (expected {entry['manifest_sha256']}, "
            f"got {actual_manifest_hash})"
        )

    try:
        manifest = load_json(manifest_path)
    except json.JSONDecodeError as exc:
        errors.append(f"{label}: manifest is not valid JSON ({exc})")
        return

    validate_against_schema(manifest, SCHEMA_DIR / "manifest.schema.json", label, errors)

    if manifest.get("id") != plugin_id:
        errors.append(f"{label}: manifest id mismatch (manifest says '{manifest.get('id')}')")
    if manifest.get("version") != version:
        errors.append(f"{label}: manifest version mismatch (manifest says '{manifest.get('version')}')")

    manifest_dir = manifest_path.parent
    seen_paths = set()
    for file_entry in manifest.get("files", []):
        rel = file_entry["path"]
        file_label = f"{label}: file '{rel}'"
        check_relative_path(rel, file_label, errors)
        if rel in seen_paths:
            errors.append(f"{label}: duplicate manifest file entry '{rel}'")
        seen_paths.add(rel)

        payload_path = manifest_dir / rel
        if not payload_path.is_file():
            errors.append(f"{file_label}: payload file missing on disk")
            continue
        actual_size = payload_path.stat().st_size
        if actual_size != file_entry["size"]:
            errors.append(f"{file_label}: size mismatch (declared {file_entry['size']}, actual {actual_size})")
        actual_hash = sha256_of(payload_path)
        if actual_hash != file_entry["sha256"]:
            errors.append(f"{file_label}: SHA-256 mismatch")

    collect_executable_payload_errors(manifest.get("files", []), label, errors)
    validate_entrypoint_files(manifest, manifest_dir, label, errors)


def validate_repository(root: Path | None = None) -> tuple[list[str], list[str]]:
    """Validate the repository. Returns (errors, warnings)."""
    global REPO_ROOT
    original_root = REPO_ROOT
    if root is not None:
        REPO_ROOT = root.resolve()

    errors: list[str] = []
    warnings: list[str] = []

    registry_path = REPO_ROOT / "registry.json"
    try:
        registry = load_json(registry_path)
    except FileNotFoundError:
        errors.append("registry.json not found at repository root")
        return errors, warnings
    except json.JSONDecodeError as exc:
        errors.append(f"registry.json is not valid JSON ({exc})")
        return errors, warnings

    validate_against_schema(registry, SCHEMA_DIR / "registry.schema.json", "registry", errors)

    seen_ids: dict[str, set] = {}
    for entry in registry.get("plugins", []):
        validate_plugin_entry(entry, seen_ids, errors, warnings)

    if root is not None:
        REPO_ROOT = original_root
    return errors, warnings


def main() -> int:
    errors, _warnings = validate_repository(REPO_ROOT)
    if errors:
        print(f"FAIL: {len(errors)} registry problem(s):")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("OK: registry is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
