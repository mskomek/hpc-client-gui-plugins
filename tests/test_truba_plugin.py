"""Fixture tests for the real, published TRUBA cluster-profile plugin.

These tests protect against accidental genericization of the TRUBA plugin
data by asserting exact values from the current hpc-client-gui defaults.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_registry import sha256_of  # noqa: E402


def load(rel_path: str):
    return json.loads((REPO_ROOT / rel_path).read_text(encoding="utf-8"))


def truba_registry_entry(version: str = "1.0.0") -> dict:
    registry = load("registry.json")
    entries = [
        p for p in registry["plugins"]
        if p["id"] == "org.hpcclient.truba" and p["version"] == version
    ]
    assert len(entries) == 1, f"exactly one TRUBA registry entry expected for {version}"
    return entries[0]


def test_registry_entry_metadata():
    entry = truba_registry_entry()
    assert entry["name"] == "TRUBA"
    assert entry["version"] == "1.0.0"
    assert entry["type"] == "cluster-profile"
    assert entry["official"] is True
    assert entry["requires_app"] == ">=1.4.0"
    assert entry["manifest_path"] == "plugins/truba/1.0.0/manifest.json"


def test_manifest_identity_and_capability():
    entry = truba_registry_entry()
    manifest = load(entry["manifest_path"])
    assert manifest["id"] == "org.hpcclient.truba"
    assert manifest["name"] == "TRUBA"
    assert manifest["version"] == "1.0.0"
    assert manifest["plugin_api"] == 1
    assert manifest["capabilities"] == ["cluster-profile"]
    assert manifest["entrypoints"]["cluster_profiles"] == ["cluster-profile.json"]
    roles = {f["role"] for f in manifest["files"]}
    assert "python" not in roles and "executable" not in roles


def test_published_hashes_match_disk():
    entry = truba_registry_entry()
    manifest = load(entry["manifest_path"])
    manifest_path = REPO_ROOT / entry["manifest_path"]
    assert sha256_of(manifest_path) == entry["manifest_sha256"]
    for file_entry in manifest["files"]:
        payload = manifest_path.parent / file_entry["path"]
        assert sha256_of(payload) == file_entry["sha256"]
        assert payload.stat().st_size == file_entry["size"]


def test_truba_profile_exact_values():
    profile = load("plugins/truba/1.0.0/cluster-profile.json")
    assert profile["schema_version"] == 1
    assert profile["profile_id"] == "truba"
    assert profile["name"] == "TRUBA"
    assert profile["scheduler"] == "slurm"

    paths = profile["paths"]
    assert paths["home_dir"] == "/arf/home/{user}"
    assert paths["scratch_dir"] == "/arf/scratch/{user}"

    commands = profile["commands"]
    assert commands["squeue_command"] == 'squeue -h -u {user} -o "%i|%P|%j|%u|%T|%M|%D|%C|%R"'
    assert commands["sbatch_command"] == "cd -- {script_dir_q} && sbatch -- {script_name_q}"
    assert commands["scancel_command"] == "scancel {job_id_q}"
    assert (
        commands["sacct_command"]
        == "sacct -u {user} --format=JobID,JobName,State,Elapsed,MaxRSS,AllocTRES"
    )
    assert commands["scontrol_command"] == "scontrol show job {job_id_q}"
    assert commands["status_command"] == "lssrv"
    assert commands["active_job_ids_command"] == 'squeue -h -u {user} -o "%A"'
    assert commands["job_state_command"] == "sacct -n -X -j {job_id_q} -o State -P"


def test_plugin_contains_no_credentials_or_hosts():
    """The plugin must never carry credentials, accounts, or hostnames."""
    profile_text = (
        (REPO_ROOT / "plugins/truba/1.0.0/cluster-profile.json").read_text(encoding="utf-8").lower()
    )
    for forbidden in ("password", "passwd", "private_key", "token", "secret", "username"):
        assert forbidden not in profile_text, f"'{forbidden}' must not appear in cluster-profile.json"

    readme = (REPO_ROOT / "plugins/truba/1.0.0/README.md").read_text(encoding="utf-8")
    assert "no credentials of any kind" in readme
    assert "not** an official TÜBİTAK ULAKBİM/TRUBA client" in readme


def test_truba_v2_profile_is_published_for_app_1_5_4():
    entry = truba_registry_entry("1.1.0")
    assert entry["requires_app"] == ">=1.5.4"
    profile = load("plugins/truba/1.1.0/cluster-profile.json")
    assert profile["schema_version"] == 2
    assert {item["id"] for item in profile["storage"]} == {"home", "scratch"}
    assert profile["quota_sources"][0]["enabled"] is False
