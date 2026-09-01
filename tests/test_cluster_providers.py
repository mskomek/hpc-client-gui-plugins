"""One registry-wide quality gate for declarative cluster providers."""

import json
from pathlib import Path

from jsonschema import Draft7Validator

from scripts.validate_registry import validate_repository

ROOT = Path(__file__).parents[1]
SCHEMA = json.loads((ROOT / "schema" / "cluster-profile.schema.json").read_text())


def test_every_cluster_provider_passes_generic_quality_gate():
    errors, _warnings = validate_repository(ROOT)
    assert errors == []
    registry = json.loads((ROOT / "registry.json").read_text())
    for entry in registry["plugins"]:
        if "cluster-profile" not in entry["capabilities"]:
            continue
        manifest = json.loads((ROOT / entry["manifest_path"]).read_text())
        profile_path = ROOT / entry["manifest_path"]
        profile = json.loads((profile_path.parent / manifest["entrypoints"]["cluster_profiles"][0]).read_text())
        assert list(Draft7Validator(SCHEMA).iter_errors(profile)) == []
        assert (profile_path.parent / "README.md").is_file()
        # Published TRUBA 1.0-1.3 packages are immutable historical payloads;
        # provenance documentation starts with a future provider version.
        if not (entry["id"] == "org.hpcclient.truba" and entry["version"] in {"1.0.0", "1.1.0", "1.2.0", "1.3.0"}):
            assert (profile_path.parent / "sources.md").is_file()
        assert all(Path(item["path"]).suffix.lower() not in {".py", ".sh", ".exe", ".dll", ".env", ".pem", ".key"} for item in manifest["files"])
