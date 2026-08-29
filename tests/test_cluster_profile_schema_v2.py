import json
from pathlib import Path

from jsonschema import Draft7Validator


SCHEMA = json.loads((Path(__file__).parents[1] / "schema" / "cluster-profile.schema.json").read_text())


def errors(profile):
    return list(Draft7Validator(SCHEMA).iter_errors(profile))


def messages(items):
    return " ".join(error.message + " " + " ".join(child.message for child in error.context) for error in items)


def test_v2_schema_accepts_structured_profile():
    profile = {
        "schema_version": 2, "profile_id": "demo", "name": "Demo", "scheduler": "slurm",
        "storage": [{"id": "home", "label": "Home", "kind": "home"}],
        "quota_sources": [{"id": "home-quota", "enabled": False}],
    }
    assert errors(profile) == []


def test_v2_schema_rejects_unknown_nested_fields():
    profile = {"schema_version": 2, "profile_id": "demo", "name": "Demo", "scheduler": "slurm",
               "site": {"secret": "not allowed"}}
    assert "secret" in messages(errors(profile))


def test_v2_schema_requires_storage_label_and_quota_id():
    profile = {"schema_version": 2, "profile_id": "demo", "name": "Demo", "scheduler": "slurm",
               "storage": [{"id": "home"}], "quota_sources": [{"enabled": False}]}
    text = messages(errors(profile))
    assert "label" in text and "id" in text
