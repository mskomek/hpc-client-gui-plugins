#!/usr/bin/env python3
"""Generate a deterministic, publishable cluster-profile package."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

SAFE_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
PLUGIN_ID = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z0-9_-]+)+$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")

def build_profile(profile_id: str, name: str, schema_version: int = 2) -> dict:
    if not SAFE_ID.fullmatch(profile_id) or not name.strip():
        raise ValueError("profile_id must be a safe non-empty ID and name is required")
    if schema_version not in (1, 2):
        raise ValueError("schema_version must be 1 or 2")
    result = {"schema_version": schema_version, "profile_id": profile_id,
              "name": name.strip(), "scheduler": "slurm"}
    if schema_version == 2:
        result.update({"storage": [], "quota_sources": []})
    return result

def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

def create_package(args: argparse.Namespace) -> Path:
    if not PLUGIN_ID.fullmatch(args.plugin_id) or not SAFE_ID.fullmatch(args.profile_id):
        raise ValueError("plugin-id must be a dotted safe ID and profile-id must match ^[a-z][a-z0-9_-]{0,63}$")
    if not SEMVER.fullmatch(args.version):
        raise ValueError("version must be semantic version X.Y.Z")
    if not args.name.strip() or not args.requires_app.strip():
        raise ValueError("name and requires-app are required")
    target = args.output_dir
    if target.exists():
        if not target.is_dir() or any(target.iterdir()):
            raise FileExistsError(f"refusing non-empty output directory: {target}")
    else:
        target.mkdir(parents=True)
    profile = build_profile(args.profile_id, args.name, 2)
    if args.template == "full":
        profile.update({"description": "Fill with verified public provider information.",
                        "metadata": {"maintainer": ""},
                        "site": {"public_name": "", "access_note": ""},
                        "scheduler_hints": {"queue_notes": "", "account_notes": ""},
                        "software": {"setup_notes": ""},
                        "storage": [{"id": kind, "label": kind.replace("-", " ").title(),
                          "kind": kind, "enabled": True, "path_template": "",
                          "access_context": "unknown", "policy": {"backup": None}}
                         for kind in ("home", "scratch", "project", "custom", "node-local")],
                        "quota_sources": [{"id": "example", "enabled": False,
                          "backend_id": "", "command_template": "", "scope": "unknown"}]})
    files = {"cluster-profile.json": json.dumps(profile, indent=2) + "\n",
             "README.md": (f"# {args.name}\n\nDeclarative cluster-profile plugin `{args.plugin_id}`.\n\n"
                           "Fill only verified public values; quota is disabled until a supported backend exists.\n")}
    for rel, body in files.items():
        (target / rel).write_text(body, encoding="utf-8", newline="\n")
    manifest = {"schema_version": 1, "plugin_api": 1, "id": args.plugin_id,
                "name": args.name.strip(), "version": args.version, "publisher": "",
                "license": "MIT", "description": "", "requires_app": args.requires_app.strip(),
                "capabilities": ["cluster-profile"],
                "entrypoints": {"cluster_profiles": ["cluster-profile.json"]}, "files": []}
    for rel in ("cluster-profile.json", "README.md"):
        data = (target / rel).read_bytes()
        manifest["files"].append({"path": rel, "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data), "role": "cluster-profile" if rel.endswith(".json") else "documentation"})
    _write_json(target / "manifest.json", manifest)
    return target

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("plugin-id", "profile-id", "name", "version", "requires-app"):
        parser.add_argument(f"--{flag}", required=True)
    parser.add_argument("--template", choices=("minimal", "full"), default="minimal")
    parser.add_argument("--output-dir", type=Path, required=True)
    create_package(parser.parse_args())
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
