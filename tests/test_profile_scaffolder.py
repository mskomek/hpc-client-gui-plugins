from argparse import Namespace
import json

from scripts.scaffold_cluster_profile import build_profile, scaffold_package


def test_scaffolder_defaults_to_v2_structured_sections():
    profile = build_profile("demo", "Demo")
    assert profile == {
        "schema_version": 2,
        "profile_id": "demo",
        "name": "Demo",
        "scheduler": "slurm",
        "storage": [],
        "quota_sources": [],
    }


def test_scaffolder_can_emit_legacy_v1():
    assert build_profile("demo", "Demo", 1) == {
        "schema_version": 1,
        "profile_id": "demo",
        "name": "Demo",
        "scheduler": "slurm",
    }


def test_scaffolder_writes_a_complete_hashed_package(tmp_path):
    output = scaffold_package(Namespace(
        plugin_id="org.hpcclient.example", profile_id="example", name="Example HPC",
        version="0.1.0", requires_app=">=1.5.0", publisher="Example contributor",
        description="Example profile.", license="MIT", template="minimal", output_dir=tmp_path,
    ))
    assert {path.name for path in output.iterdir()} == {"manifest.json", "cluster-profile.json", "README.md"}
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["entrypoints"] == {"cluster_profiles": ["cluster-profile.json"]}
    assert all(item["sha256"] and item["size"] for item in manifest["files"])
