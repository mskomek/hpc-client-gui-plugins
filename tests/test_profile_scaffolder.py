from scripts.scaffold_cluster_profile import build_profile


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
