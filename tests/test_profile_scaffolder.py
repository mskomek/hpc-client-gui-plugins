import json

import pytest

from scripts.scaffold_cluster_profile import build_profile, create_package


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


def test_scaffolder_creates_valid_complete_package(tmp_path):
    class Args:
        plugin_id = "org.hpcclient.example"
        profile_id = "example"
        name = "Example HPC"
        version = "0.1.0"
        requires_app = ">=1.5.4"
        publisher = "Example contributor"
        description = "Fictional offline provider."
        template = "full"
        output_dir = tmp_path / "example" / "0.1.0"

    target = create_package(Args())
    assert {path.name for path in target.iterdir()} == {"cluster-profile.json", "README.md", "manifest.json"}
    manifest = json.loads((target / "manifest.json").read_text())
    assert manifest["publisher"]
    assert manifest["description"]
    for entry in manifest["files"]:
        data = (target / entry["path"]).read_bytes()
        assert entry["size"] == len(data)


def test_scaffolder_refuses_invalid_or_nonempty_targets(tmp_path):
    class Args:
        plugin_id = "org.hpcclient.example"
        profile_id = "example"
        name = "Example HPC"
        version = "01.2.3"
        requires_app = ">=1.5.4"
        publisher = "Example contributor"
        description = "Fictional offline provider."
        template = "minimal"
        output_dir = tmp_path / "target"

    with pytest.raises(ValueError):
        create_package(Args())
    Args.version = "0.1.0"
    Args.output_dir.mkdir()
    (Args.output_dir / "existing.txt").write_text("x")
    with pytest.raises(FileExistsError):
        create_package(Args())
