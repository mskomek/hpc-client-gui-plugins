#!/usr/bin/env python3
"""Create a minimal declarative cluster-profile payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_profile(profile_id: str, name: str, schema_version: int = 2) -> dict:
    if not profile_id or not name:
        raise ValueError("profile_id and name are required")
    if schema_version not in (1, 2):
        raise ValueError("schema_version must be 1 or 2")
    profile = {
        "schema_version": schema_version,
        "profile_id": profile_id,
        "name": name,
        "scheduler": "slurm",
    }
    if schema_version == 2:
        profile["storage"] = []
        profile["quota_sources"] = []
    return profile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--schema-version", type=int, choices=(1, 2), default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(build_profile(args.profile_id, args.name, args.schema_version), indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
