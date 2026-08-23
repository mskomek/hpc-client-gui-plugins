"""Registry validation tests for the official HPC Client GUI plugin registry."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from validate_registry import validate_repository  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_file(root: Path, rel: str, data: bytes) -> dict:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {
        "path": rel,
        "sha256": sha256_bytes(data),
        "size": len(data),
        "role": "documentation",
    }


def cluster_profile_payload() -> bytes:
    payload = {
        "schema_version": 1,
        "profile_id": "example",
        "name": "Example Cluster",
        "scheduler": "slurm",
        "paths": {"home_dir": "/home/{user}", "scratch_dir": "/scratch/{user}"},
        "commands": {"squeue_command": 'squeue -h -u {user} -o "%i"'},
    }
    return json.dumps(payload, indent=2).encode()


def lint_index_payload(rule_payload: bytes) -> tuple[bytes, dict]:
    rule_entry = {
        "path": "rules.json",
        "sha256": sha256_bytes(rule_payload),
    }
    index = {
        "schema_version": 1,
        "tool": "fluent-journal",
        "rules": [{"id": "toto-in-journal", "severity": "error", "summary": "TUI command found"}],
        "rule_files": [rule_entry],
    }
    return json.dumps(index, indent=2).encode(), rule_entry


def template_index_payload(body: bytes) -> tuple[bytes, dict]:
    content_entry = {
        "path": "template.json",
        "sha256": sha256_bytes(body),
    }
    index = {
        "schema_version": 1,
        "templates": [
                {
                    "id": "sbatch-basic",
                    "name": "Basic sbatch script",
                    "scheduler": "slurm",
                    "content_path": "template.json",
                    "sha256": content_entry["sha256"],
                }
        ],
    }
    return json.dumps(index, indent=2).encode(), content_entry


def make_manifest(
    *,
    plugin_id: str = "org.hpcclient.test",
    version: str = "1.0.0",
    capabilities: list | None = None,
    files: list | None = None,
    entrypoints: dict | None = None,
    **overrides,
) -> dict:
    manifest = {
        "schema_version": 1,
        "plugin_api": 1,
        "id": plugin_id,
        "name": "Test Plugin",
        "version": version,
        "publisher": "HPC Client GUI",
        "license": "MIT",
        "description": "A test plugin.",
        "requires_app": ">=1.4.0",
        "capabilities": capabilities or ["cluster-profile"],
        "entrypoints": entrypoints if entrypoints is not None else {},
        "files": files or [],
    }
    manifest.update(overrides)
    return manifest


def add_plugin(
    root: Path,
    *,
    plugin_id: str = "org.hpcclient.test",
    version: str = "1.0.0",
    capabilities: list | None = None,
    manifest_overrides: dict | None = None,
    registry_entry_overrides: dict | None = None,
) -> dict:
    """Create a complete, self-consistent single-plugin layout under root."""
    base = f"plugins/{plugin_id.split('.')[-1]}/{version}"
    capabilities = capabilities if capabilities is not None else ["cluster-profile"]

    extra_files: list[dict] = []
    entrypoints: dict = {}

    profile_data = cluster_profile_payload()
    profile_entry = write_file(root, f"{base}/cluster-profile.json", profile_data)
    profile_entry["role"] = "cluster-profile"

    for capability in capabilities:
        if capability == "cluster-profile":
            entrypoints.setdefault("cluster_profiles", []).append("cluster-profile.json")
        elif capability == "lint-rules":
            rule_payload = json.dumps(
                {
                    "schema_version": 1,
                    "tool": "fluent-journal",
                    "rules": [
                        {
                            "id": "tui-command",
                            "severity": "error",
                            "message": "TUI commands cannot run in batch journals.",
                            "match": {"kind": "forbidden-keyword", "value": "/gui/mesh"},
                        }
                    ],
                },
                indent=2,
            ).encode()
            rule_entry = write_file(root, f"{base}/rules.json", rule_payload)
            rule_entry["role"] = "lint-rules"
            index_bytes, _ = lint_index_payload(rule_payload)
            index_entry = write_file(root, f"{base}/lint-index.json", index_bytes)
            index_entry["role"] = "lint-index"
            # Recompute the rule hash now that the real file exists.
            index_obj = json.loads(index_bytes)
            index_obj["rule_files"] = [
                {"path": "rules.json", "sha256": sha256_bytes(rule_payload)}
            ]
            index_bytes = json.dumps(index_obj, indent=2).encode()
            (root / f"{base}/lint-index.json").write_bytes(index_bytes)
            index_entry["sha256"] = sha256_bytes(index_bytes)
            index_entry["size"] = len(index_bytes)
            extra_files.extend([rule_entry, index_entry])
            entrypoints["lint_index"] = "lint-index.json"
        elif capability in {"job-template", "application-tools"}:
            body = json.dumps(
                {
                    "schema_version": 1,
                    "id": "sbatch-basic",
                    "title": "Basic sbatch script",
                    "body": "#!/bin/bash\n#SBATCH --time=01:00:00\n",
                },
                indent=2,
            ).encode()
            content_entry = write_file(root, f"{base}/template.json", body)
            content_entry["role"] = "template-content"
            index_bytes, _ = template_index_payload(b"unused")
            index_obj = json.loads(index_bytes)
            index_obj["templates"][0]["sha256"] = sha256_bytes(body)
            index_bytes = json.dumps(index_obj, indent=2).encode()
            index_entry = write_file(root, f"{base}/template-index.json", index_bytes)
            index_entry["role"] = "template-index"
            index_entry["sha256"] = sha256_bytes(index_bytes)
            index_entry["size"] = len(index_bytes)
            extra_files.extend([content_entry, index_entry])
            entrypoints["template_index"] = "template-index.json"

    files = [profile_entry] + extra_files
    for file_entry in files:
        # Manifest file paths are relative to the manifest directory.
        file_entry["path"] = file_entry["path"].removeprefix(base + "/")
        disk_path = root / base / file_entry["path"]
        file_entry["size"] = disk_path.stat().st_size
        file_entry["sha256"] = sha256_bytes(disk_path.read_bytes())

    manifest = make_manifest(
        plugin_id=plugin_id,
        version=version,
        capabilities=capabilities,
        files=files,
        entrypoints=entrypoints,
    )
    if manifest_overrides:
        manifest.update(manifest_overrides)

    manifest_rel = f"{base}/manifest.json"
    manifest_bytes = json.dumps(manifest, indent=2).encode()
    manifest_path = root / manifest_rel
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(manifest_bytes)

    entry = {
        "id": plugin_id,
        "name": "Test Plugin",
        "version": version,
        "plugin_api": 1,
        "type": capabilities[0],
        "description": "A test plugin.",
        "publisher": "HPC Client GUI",
        "requires_app": ">=1.4.0",
        "manifest_path": manifest_rel,
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "official": True,
    }
    entry.update(registry_entry_overrides or {})
    return entry


def build_registry(root: Path, plugins: list[dict]) -> None:
    registry = {
        "schema_version": 1,
        "plugin_api": 1,
        "repository": {
            "owner": "mskomek",
            "name": "hpc-client-gui-plugins",
            "raw_base": "https://raw.githubusercontent.com/mskomek/hpc-client-gui-plugins/main/",
        },
        "plugins": plugins,
    }
    (root / "registry.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")


def run_validator(root: Path):
    errors, warnings = validate_repository(root)
    return errors, warnings


# ---------------------------------------------------------------------------
# Valid registries
# ---------------------------------------------------------------------------


def test_empty_registry_is_valid(tmp_path):
    build_registry(tmp_path, [])
    errors, _ = run_validator(tmp_path)
    assert errors == []


def test_single_valid_cluster_profile_plugin(tmp_path):
    entry = add_plugin(tmp_path)
    build_registry(tmp_path, [entry])
    errors, _ = run_validator(tmp_path)
    assert errors == []


def test_multiple_versions_of_same_plugin(tmp_path):
    entry_v1 = add_plugin(tmp_path, version="1.0.0")
    entry_v2 = add_plugin(tmp_path, version="1.1.0")
    build_registry(tmp_path, [entry_v1, entry_v2])
    errors, _ = run_validator(tmp_path)
    assert errors == []


def test_nested_data_files_are_allowed(tmp_path):
    entry = add_plugin(
        tmp_path,
        plugin_id="org.hpcclient.nested",
        capabilities=["lint-rules"],
    )
    build_registry(tmp_path, [entry])
    errors, _ = run_validator(tmp_path)
    assert errors == []


# ---------------------------------------------------------------------------
# Invalid registries
# ---------------------------------------------------------------------------


def expect_failure(tmp_path, plugins, needle: str):
    build_registry(tmp_path, plugins)
    errors, _ = run_validator(tmp_path)
    assert errors, "expected validator failure"
    joined = "\n".join(errors)
    assert needle in joined, f"expected '{needle}' in:\n{joined}"
    return errors


def test_duplicate_plugin_id_and_version_rejected(tmp_path):
    entry = add_plugin(tmp_path)
    expect_failure(
        tmp_path,
        [entry, dict(entry)],
        "duplicate registry entry for plugin org.hpcclient.test@1.0.0",
    )


def test_malformed_semver_rejected(tmp_path):
    entry = add_plugin(tmp_path, registry_entry_overrides={"version": "not-a-version"})
    expect_failure(tmp_path, [entry], "not a valid semantic version")


def test_bad_manifest_sha_rejected(tmp_path):
    entry = add_plugin(tmp_path)
    entry["manifest_sha256"] = "0" * 64
    expect_failure(tmp_path, [entry], "manifest SHA-256 mismatch")


@pytest.mark.parametrize("bad_sha", ["Z" * 64, "abc123", ""], ids=["nonhex", "short", "empty"])
def test_bad_sha_format_rejected_by_schema(tmp_path, bad_sha):
    entry = add_plugin(tmp_path)
    entry["manifest_sha256"] = bad_sha
    expect_failure(tmp_path, [entry], "does not match")


def test_missing_manifest_rejected(tmp_path):
    entry = add_plugin(tmp_path)
    (tmp_path / entry["manifest_path"]).unlink()
    expect_failure(tmp_path, [entry], "manifest not found")


def test_manifest_id_mismatch_rejected(tmp_path):
    entry = add_plugin(tmp_path)
    manifest_path = tmp_path / entry["manifest_path"]
    manifest = json.loads(manifest_path.read_text())
    manifest["id"] = "org.hpcclient.other"
    data = json.dumps(manifest, indent=2).encode()
    manifest_path.write_bytes(data)
    expect_failure(tmp_path, [entry], "manifest id mismatch")


def test_manifest_version_mismatch_rejected(tmp_path):
    entry = add_plugin(tmp_path)
    manifest_path = tmp_path / entry["manifest_path"]
    manifest = json.loads(manifest_path.read_text())
    manifest["version"] = "9.9.9"
    data = json.dumps(manifest, indent=2).encode()
    manifest_path.write_bytes(data)
    expect_failure(tmp_path, [entry], "manifest version mismatch")


def test_missing_payload_file_rejected(tmp_path):
    entry = add_plugin(tmp_path)
    (tmp_path / entry["manifest_path"]).parent.joinpath("cluster-profile.json").unlink()
    expect_failure(tmp_path, [entry], "payload file missing on disk")


def test_wrong_payload_size_rejected(tmp_path):
    entry = add_plugin(tmp_path)
    manifest_path = tmp_path / entry["manifest_path"]
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][0]["size"] += 1
    data = json.dumps(manifest, indent=2).encode()
    manifest_path.write_bytes(data)
    expect_failure(tmp_path, [entry], "size mismatch")


def test_wrong_payload_hash_rejected(tmp_path):
    entry = add_plugin(tmp_path)
    manifest_path = tmp_path / entry["manifest_path"]
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][0]["sha256"] = "f" * 64
    data = json.dumps(manifest, indent=2).encode()
    manifest_path.write_bytes(data)
    expect_failure(tmp_path, [entry], "SHA-256 mismatch")


def test_parent_traversal_in_manifest_path_rejected(tmp_path):
    entry = add_plugin(tmp_path, registry_entry_overrides={"manifest_path": "../outside/manifest.json"})
    expect_failure(tmp_path, [entry], "'..' segment is not allowed")


def test_windows_absolute_manifest_path_rejected(tmp_path):
    entry = add_plugin(
        tmp_path,
        registry_entry_overrides={"manifest_path": "C:/plugins/truba/manifest.json"},
    )
    expect_failure(tmp_path, [entry], "Windows drive-style path")


def test_posix_absolute_manifest_path_rejected(tmp_path):
    entry = add_plugin(
        tmp_path,
        registry_entry_overrides={"manifest_path": "/etc/manifest.json"},
    )
    expect_failure(tmp_path, [entry], "absolute POSIX path")


def test_duplicate_manifest_file_entries_rejected(tmp_path):
    entry = add_plugin(tmp_path)
    manifest_path = tmp_path / entry["manifest_path"]
    manifest = json.loads(manifest_path.read_text())
    manifest["files"].append(dict(manifest["files"][0]))
    data = json.dumps(manifest, indent=2).encode()
    manifest_path.write_bytes(data)
    expect_failure(tmp_path, [entry], "duplicate manifest file entry")


def test_unsupported_capability_rejected(tmp_path):
    entry = add_plugin(tmp_path, manifest_overrides={"capabilities": ["remote-execution"]})
    expect_failure(tmp_path, [entry], "is not one of")


def test_executable_role_rejected_by_schema(tmp_path):
    entry = add_plugin(tmp_path)
    manifest_path = tmp_path / entry["manifest_path"]
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][0]["role"] = "python"
    data = json.dumps(manifest, indent=2).encode()
    manifest_path.write_bytes(data)
    expect_failure(tmp_path, [entry], "is not one of")


def test_executable_looking_extension_rejected(tmp_path):
    entry = add_plugin(tmp_path)
    manifest_path = tmp_path / entry["manifest_path"]
    manifest = json.loads(manifest_path.read_text())
    base = str(Path(entry["manifest_path"]).parent)
    script = write_file(tmp_path, f"{base}/helper.py", b"print('hi')\n")
    script["path"] = "helper.py"
    script["role"] = "documentation"
    manifest["files"].append(script)
    data = json.dumps(manifest, indent=2).encode()
    manifest_path.write_bytes(data)
    expect_failure(tmp_path, [entry], "executable-looking extension")


# ---------------------------------------------------------------------------
# Registry/manifest identity and compatibility agreement
# ---------------------------------------------------------------------------


def _rewrite_manifest(tmp_path, entry, mutate) -> None:
    manifest_path = tmp_path / entry["manifest_path"]
    manifest = json.loads(manifest_path.read_text())
    mutate(manifest)
    manifest_path.write_bytes(json.dumps(manifest, indent=2).encode())


def test_manifest_name_mismatch_rejected(tmp_path):
    entry = add_plugin(tmp_path)
    _rewrite_manifest(
        tmp_path, entry, lambda m: m.update({"name": "Different Name"})
    )
    expect_failure(tmp_path, [entry], "manifest name mismatch")


def test_manifest_publisher_mismatch_rejected(tmp_path):
    entry = add_plugin(tmp_path)
    _rewrite_manifest(
        tmp_path, entry, lambda m: m.update({"publisher": "Someone Else"})
    )
    expect_failure(tmp_path, [entry], "manifest publisher mismatch")


def test_manifest_plugin_api_mismatch_rejected(tmp_path):
    entry = add_plugin(tmp_path)
    _rewrite_manifest(tmp_path, entry, lambda m: m.update({"plugin_api": 2}))
    expect_failure(tmp_path, [entry], "manifest plugin_api mismatch")


def test_manifest_requires_app_mismatch_rejected(tmp_path):
    entry = add_plugin(tmp_path)
    _rewrite_manifest(tmp_path, entry, lambda m: m.update({"requires_app": ">=99.0.0"}))
    expect_failure(tmp_path, [entry], "manifest requires_app mismatch")


def test_registry_capabilities_mismatch_rejected(tmp_path):
    entry = add_plugin(
        tmp_path,
        registry_entry_overrides={"capabilities": ["lint-rules", "job-template"]},
    )
    expect_failure(
        tmp_path,
        [entry],
        "do not match manifest capabilities ['cluster-profile']",
    )


def test_matching_registry_capabilities_accepted(tmp_path):
    entry = add_plugin(
        tmp_path,
        capabilities=["cluster-profile"],
        registry_entry_overrides={"capabilities": ["cluster-profile"]},
    )
    build_registry(tmp_path, [entry])
    errors, _ = run_validator(tmp_path)
    assert errors == []


def test_manifest_path_outside_version_directory_rejected(tmp_path):
    entry = add_plugin(tmp_path, version="1.0.0")
    entry["manifest_path"] = "plugins/test/2.0.0/manifest.json"
    expect_failure(
        tmp_path,
        [entry],
        "does not point into its own version directory",
    )


# ---------------------------------------------------------------------------
# Capability/entrypoint consistency
# ---------------------------------------------------------------------------


def test_capability_without_entrypoint_rejected(tmp_path):
    entry = add_plugin(tmp_path, capabilities=["lint-rules"])
    _rewrite_manifest(
        tmp_path, entry, lambda m: m.update({"entrypoints": {}})
    )
    expect_failure(
        tmp_path,
        [entry],
        "capability 'lint-rules' is declared but none of the entrypoints",
    )


def test_entrypoint_key_without_capability_rejected(tmp_path):
    entry = add_plugin(tmp_path, capabilities=["cluster-profile"])
    _rewrite_manifest(
        tmp_path,
        entry,
        lambda m: m.update({"entrypoints": {"cluster_profiles": ["cluster-profile.json"], "lint_index": "missing.json"}}),
    )
    # Keep the registry hash in sync so the identity checks are what fail.
    manifest_path = tmp_path / entry["manifest_path"]
    entry["manifest_sha256"] = sha256_bytes(manifest_path.read_bytes())
    expect_failure(
        tmp_path,
        [entry],
        "entrypoint 'lint_index' has no matching declared capability",
    )


def test_job_templates_entrypoint_key_accepted(tmp_path):
    entry = add_plugin(tmp_path, capabilities=["job-template"])
    # Rewrite the template index entrypoint to the equivalent alias key.
    manifest_path = tmp_path / entry["manifest_path"]
    manifest = json.loads(manifest_path.read_text())
    manifest["entrypoints"] = {
        "job_templates": [manifest["entrypoints"]["template_index"]]
    }
    data = json.dumps(manifest, indent=2).encode()
    manifest_path.write_bytes(data)
    entry["manifest_sha256"] = sha256_bytes(data)

    build_registry(tmp_path, [entry])
    errors, _ = run_validator(tmp_path)
    assert errors == []


def test_job_template_capability_with_wrong_index_role_rejected(tmp_path):
    entry = add_plugin(tmp_path, capabilities=["job-template"])
    _rewrite_manifest(
        tmp_path,
        entry,
        lambda m: m.update(
            {"files": [{**f, "role": "documentation"} for f in m["files"]]}
        ),
    )
    expect_failure(tmp_path, [entry], "does not match expected")
