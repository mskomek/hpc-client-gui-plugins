#!/usr/bin/env python3
"""Create a declarative cluster-profile plugin package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def build_profile(profile_id: str, name: str, schema_version: int = 2) -> dict:
    if not profile_id or not name:
        raise ValueError("profile_id and name are required")
    if schema_version not in (1, 2):
        raise ValueError("schema_version must be 1 or 2")
    profile = {"schema_version": schema_version, "profile_id": profile_id, "name": name, "scheduler": "slurm"}
    if schema_version == 2:
        profile["storage"] = []
        profile["quota_sources"] = []
    return profile


def _full_profile(profile_id: str, name: str) -> dict:
    profile = build_profile(profile_id, name)
    profile.update({
        "description": "",
        "metadata": {"maintainer": ""},
        "site": {"public_name": name, "region": "", "access_note": ""},
        "scheduler_hints": {"queue_notes": "", "account_notes": "", "partitions": []},
        "software": {"module_paths": [], "setup_notes": ""},
    })
    return profile


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scaffold_package(args: argparse.Namespace) -> Path:
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    profile = _full_profile(args.profile_id, args.name) if args.template == "full" else build_profile(args.profile_id, args.name)
    profile["description"] = args.description
    (output_dir / "cluster-profile.json").write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    (output_dir / "README.md").write_text(
        f"# {args.name}\n\n{args.description}\n\n"
        "This declarative profile contains no credentials and installs nothing on the cluster.\n",
        encoding="utf-8",
    )
    files = []
    for path, role in (("cluster-profile.json", "cluster-profile"), ("README.md", "documentation")):
        file_path = output_dir / path
        files.append({"path": path, "sha256": _sha256(file_path), "size": file_path.stat().st_size, "role": role})
    manifest = {
        "schema_version": 1, "plugin_api": 1, "id": args.plugin_id, "name": args.name,
        "version": args.version, "publisher": args.publisher, "license": args.license,
        "description": args.description, "requires_app": args.requires_app,
        "capabilities": ["cluster-profile"], "entrypoints": {"cluster_profiles": ["cluster-profile.json"]},
        "files": files,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-id", default="org.hpcclient.site")
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--requires-app", default=">=1.5.0")
    parser.add_argument("--publisher", default="HPC Client GUI contributor")
    parser.add_argument("--description", default="Cluster profile.")
    parser.add_argument("--license", default="MIT")
    parser.add_argument("--template", choices=("minimal", "full"), default="minimal")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--output", type=Path, help="Write only the profile JSON (legacy mode).")
    args = parser.parse_args()
    if args.output_dir is None:
        if args.output is None:
            parser.error("one of --output-dir or --output is required")
        args.output.write_text(json.dumps(build_profile(args.profile_id, args.name), indent=2) + "\n", encoding="utf-8")
        return 0
    scaffold_package(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
