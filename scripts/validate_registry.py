#!/usr/bin/env python3
"""Validate the official HPC Client GUI plugin registry.

Checks, in order:
1. registry.json loads and validates against schema/registry.schema.json;
2. plugin IDs and (id, version) pairs are unique;
3. each referenced manifest exists locally inside its immutable
   ``plugins/<id>/<version>/`` directory and its SHA-256 matches the
   registry entry;
4. each manifest validates against schema/manifest.schema.json;
5. registry/manifest identity and compatibility data agree: id, version,
   name, publisher, plugin_api, requires_app, and declared capabilities
   (``capabilities`` is authoritative for multi-capability plugins; the
   single legacy ``type`` field is kept for display compatibility);
6. every declared file exists with the declared size and SHA-256;
7. payloads are declarative data (no executable-looking files), with one
   Plugin API v2 exception: capability 'linter-tool' plugins may ship
   Python engine files, every one of which must carry the
   'linter-engine' role and is hash-pinned like any other payload;
8. capability entrypoints are consistent with declared capabilities and
   their payloads validate against their role schemas;
9. version directories contain no undeclared extra files (immutable,
   fully-enumerated directories).

Plugin API v1 stays declarative-only: no Python modules, no executable
hooks, no binaries, no installation-time command execution, exact-file
downloads only, strict response-size and total-size limits. Plugin API
v2 adds the hash-verified 'linter-tool' engine files; nothing executes
at install time - engines load lazily and defensively at use time.

Exit status is non-zero on any error.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath

try:
    from jsonschema import Draft7Validator
    from packaging.specifiers import InvalidSpecifier, SpecifierSet
    from packaging.version import InvalidVersion, Version
except ImportError:  # pragma: no cover
    print("Missing dependencies. Run: pip install jsonschema packaging", file=sys.stderr)
    raise SystemExit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schema"

ALLOWED_PAYLOAD_EXTENSIONS = {".json", ".md", ".txt", ".tpl"}

# Plugin API v2 (capability 'linter-tool') may additionally ship verified
# Python engine files. Every .py file MUST carry the 'linter-engine' role,
# and that role is only valid under plugin_api 2.
V2_EXTRA_PAYLOAD_EXTENSIONS = {".py"}
LINTER_ENGINE_ROLE = "linter-engine"
LINTER_DATA_ROLE = "linter-data"

SCHEMA_FOR_ROLE = {
    "cluster-profile": "cluster-profile.schema.json",
    "lint-index": "lint-index.schema.json",
    "lint-rules": "lint-rule.schema.json",
    "template-index": "template-index.schema.json",
    "template-content": "template.schema.json",
}

# Capability -> entrypoint keys that may satisfy it. ``job_templates`` and
# ``template_index`` are equivalent index entrypoints for template packs.
CAPABILITY_ENTRYPOINT_KEYS = {
    "cluster-profile": ("cluster_profiles",),
    "lint-rules": ("lint_index",),
    "job-template": ("template_index", "job_templates"),
    "application-tools": ("template_index", "job_templates"),
    "linter-tool": ("linter_engine",),
}

ENTRYPOINT_ROLES = {
    "cluster_profiles": ("cluster-profile",),
    "lint_index": ("lint-index",),
    "template_index": ("template-index",),
    "job_templates": ("template-index",),
    "linter_engine": ("linter-engine",),
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
    if role == "cluster-profile":
        errors.extend(f"{label}: {problem}" for problem in validate_cluster_profile(instance))


def validate_cluster_profile(profile: object) -> list[str]:
    """Semantic checks Draft 7 cannot express for v2 provider payloads."""
    if not isinstance(profile, dict) or profile.get("schema_version") != 2:
        return []
    errors: list[str] = []
    safe_id = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
    for section, label in ((profile.get("storage"), "storage"), (profile.get("quota_sources"), "quota_sources")):
        ids: set[str] = set()
        for index, item in enumerate(section or []):
            if not isinstance(item, dict):
                continue
            ident = item.get("id")
            if not isinstance(ident, str) or not safe_id.fullmatch(ident):
                errors.append(f"{label}[{index}].id must match {safe_id.pattern}")
            elif ident in ids:
                errors.append(f"duplicate {label} id '{ident}'")
            ids.add(ident)
            if label == "storage" and item.get("kind") not in {None, "home", "scratch", "project", "custom", "node-local"}:
                errors.append(f"storage[{index}].kind is unsupported")
            if label == "storage" and item.get("access_context") not in {None, "login-node", "shared", "compute-node", "unknown"}:
                errors.append(f"storage[{index}].access_context is unsupported")
            if label == "quota_sources":
                if item.get("scope") not in {None, "user", "group", "project", "unknown"}:
                    errors.append(f"quota_sources[{index}].scope is unsupported")
                command = item.get("command_template")
                if isinstance(command, str) and any(ord(c) < 32 and c not in "\t" for c in command):
                    errors.append(f"quota_sources[{index}].command_template contains control characters")
                if isinstance(command, str) and ("\n" in command or "\r" in command):
                    errors.append(f"quota_sources[{index}].command_template must be single-line")
    storage = profile.get("storage") or []
    source_ids = {item.get("id") for item in (profile.get("quota_sources") or []) if isinstance(item, dict)}
    for index, item in enumerate(storage):
        if isinstance(item, dict) and item.get("quota_source_id") and item["quota_source_id"] not in source_ids:
            errors.append(f"storage[{index}].quota_source_id references an unknown source")
    paths = profile.get("paths") or {}
    for alias, kind in (("home_dir", "home"), ("scratch_dir", "scratch")):
        alias_value = paths.get(alias)
        matches = [item.get("path_template") for item in storage if isinstance(item, dict) and item.get("kind") == kind]
        if alias_value and matches and any(value and value != alias_value for value in matches):
            errors.append(f"paths.{alias} conflicts with structured {kind} storage")
    return errors


def validate_entrypoint_files(manifest: dict, manifest_dir: Path, label: str, errors: list[str]) -> None:
    capabilities = set(manifest.get("capabilities", []))
    entrypoints = manifest.get("entrypoints", {})
    declared_files = {entry["path"]: entry for entry in manifest.get("files", [])}

    # Every entrypoint key must be justified by a matching capability.
    allowed_keys = {
        key
        for capability in capabilities
        for key in CAPABILITY_ENTRYPOINT_KEYS.get(capability, ())
    }
    for key in entrypoints:
        if key not in allowed_keys:
            errors.append(
                f"{label}: entrypoint '{key}' has no matching declared capability"
            )

    for capability in sorted(capabilities):
        acceptable_keys = CAPABILITY_ENTRYPOINT_KEYS.get(capability)
        if acceptable_keys is None:
            continue
        present_keys = [key for key in acceptable_keys if entrypoints.get(key)]
        if not present_keys:
            errors.append(
                f"{label}: capability '{capability}' is declared but none of the "
                f"entrypoints {list(acceptable_keys)} provide it"
            )
            continue
        for key in present_keys:
            raw_entries = entrypoints.get(key)
            if isinstance(raw_entries, str):
                raw_entries = [raw_entries]
            for entry_rel in raw_entries or []:
                entry_label = f"{label}: entrypoint '{key}' -> '{entry_rel}'"
                errors_before = len(errors)
                check_relative_path(entry_rel, entry_label, errors)
                if len(errors) > errors_before:
                    continue
                file_entry = declared_files.get(entry_rel)
                if file_entry is None:
                    errors.append(f"{entry_label}: not declared in manifest.files")
                    continue
                if file_entry.get("role") not in ENTRYPOINT_ROLES[key]:
                    errors.append(
                        f"{entry_label}: role '{file_entry.get('role')}' does not "
                        f"match expected {ENTRYPOINT_ROLES[key]}"
                    )
                    continue
                payload_path = manifest_dir / entry_rel
                if payload_path.is_file():
                    validate_payload_role(file_entry["role"], payload_path, entry_label, errors)


def collect_executable_payload_errors(
    files: list[dict],
    label: str,
    errors: list[str],
    plugin_api: int = 1,
) -> None:
    allowed = set(ALLOWED_PAYLOAD_EXTENSIONS)
    if plugin_api == 2:
        allowed |= V2_EXTRA_PAYLOAD_EXTENSIONS
    for entry in files:
        suffix = Path(entry["path"]).suffix.lower()
        role = entry.get("role")
        if suffix not in allowed:
            errors.append(
                f"{label}: payload '{entry['path']}' has executable-looking extension "
                f"'{suffix or '<none>'}'; Plugin API {plugin_api} allows only "
                f"{sorted(allowed)}"
            )
            continue
        if plugin_api == 2 and suffix == ".py" and role != LINTER_ENGINE_ROLE:
            errors.append(
                f"{label}: payload '{entry['path']}' is Python but has role "
                f"'{role}'; under Plugin API v2 every .py file must use the "
                f"'{LINTER_ENGINE_ROLE}' role"
            )
        if role == LINTER_ENGINE_ROLE and (plugin_api != 2 or suffix != ".py"):
            errors.append(
                f"{label}: payload '{entry['path']}' uses role '{LINTER_ENGINE_ROLE}' "
                f"which requires Plugin API v2 and a .py extension"
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
    if len(errors) == errors_before:
        # Published versions are immutable directories: a registry entry
        # must point into a per-version directory named exactly after the
        # declared version, so entries can never cross version directories.
        parent_name = PurePosixPath(manifest_rel).parent.name
        if parent_name != version:
            errors.append(
                f"{label}: manifest_path '{manifest_rel}' does not point into "
                f"its own version directory ('{parent_name}' != '{version}')"
            )
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
    if manifest.get("name") != entry["name"]:
        errors.append(
            f"{label}: manifest name mismatch (manifest says '{manifest.get('name')}')"
        )
    if manifest.get("publisher") != entry["publisher"]:
        errors.append(
            f"{label}: manifest publisher mismatch (manifest says '{manifest.get('publisher')}')"
        )
    if manifest.get("plugin_api") != entry["plugin_api"]:
        errors.append(
            f"{label}: manifest plugin_api mismatch (manifest says '{manifest.get('plugin_api')}')"
        )
    if manifest.get("requires_app") != entry["requires_app"]:
        errors.append(
            f"{label}: manifest requires_app mismatch "
            f"(manifest says '{manifest.get('requires_app')}')"
        )
    registry_capabilities = entry.get("capabilities")
    if isinstance(registry_capabilities, list):
        # ``capabilities`` is authoritative for multi-capability plugins;
        # the single legacy ``type`` field is display-only compatibility.
        if sorted(str(item) for item in registry_capabilities) != sorted(
            str(item) for item in manifest.get("capabilities", [])
        ):
            errors.append(
                f"{label}: registry capabilities {registry_capabilities} do not "
                f"match manifest capabilities {manifest.get('capabilities')}"
            )

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

    # Version directories are immutable and fully enumerated: every file on
    # disk must be declared in manifest.files. Undeclared extras (including
    # unreferenced .tpl templates) are rejected so clients that download
    # exactly the declared files never miss content. Local Python bytecode
    # caches are runtime artifacts, never published content: they surface as
    # warnings (hygiene signal) instead of failing local validation.
    for existing in sorted(manifest_dir.rglob("*")):
        if not existing.is_file():
            continue
        rel = existing.relative_to(manifest_dir).as_posix()
        if rel == "manifest.json" or rel in seen_paths:
            continue
        if "__pycache__" in PurePosixPath(rel).parts or rel.endswith(".pyc"):
            warnings.append(
                f"{label}: local bytecode cache present on disk (never commit "
                f"it): '{rel}'"
            )
            continue
        errors.append(
            f"{label}: undeclared extra file in version directory '{rel}' "
            "(every file must be listed in manifest.files)"
        )

    collect_executable_payload_errors(
        manifest.get("files", []), label, errors, int(manifest.get("plugin_api", 1))
    )
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
