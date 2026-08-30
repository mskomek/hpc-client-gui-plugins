import json
import re
from pathlib import Path

from scripts.validate_registry import validate_cluster_profile


def test_tutorial_profile_example_matches_provider_validator():
    guide = Path("docs/ADDING_CLUSTER_PROVIDER.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)\n```", guide, re.DOTALL)
    profile = next(json.loads(block) for block in blocks if '"profile_id": "example"' in block)

    assert validate_cluster_profile(profile) == []
    assert {area["access_context"] for area in profile["storage"]} == {"login-node"}


def test_tutorial_separates_scheduler_and_quota_placeholders():
    guide = Path("docs/ADDING_CLUSTER_PROVIDER.md").read_text(encoding="utf-8")

    assert "### Scheduler command placeholders" in guide
    assert "### Quota command placeholders" in guide
    assert "`{user}`, `{subject}`, `{path}`," in guide
    assert "`backend_id` must name a reviewed backend already allow-listed" in guide
