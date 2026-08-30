#!/usr/bin/env python3
<<<<<<< HEAD
"""Create a declarative cluster-profile plugin package."""

=======
"""Generate and validate a deterministic cluster-profile plugin package."""
>>>>>>> origin/main
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from scripts.validate_registry import validate_against_schema, validate_cluster_profile

PLUGIN_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z0-9]+)+$")
PROFILE_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def build_profile(profile_id: str, name: str, schema_version: int = 2) -> dict:
    if not PROFILE_ID_RE.fullmatch(profile_id) or not name.strip():
        raise ValueError("profile_id must be a safe non-empty ID and name is required")
    if schema_version not in (1, 2):
        raise ValueError("schema_version must be 1 or 2")
<<<<<<< HEAD
    profile = {"schema_version": schema_version, "profile_id": profile_id, "name": name, "scheduler": "slurm"}
=======
    result = {"schema_version": schema_version, "profile_id": profile_id,
              "name": name.strip(), "scheduler": "slurm"}
>>>>>>> origin/main
    if schema_version == 2:
        result.update({"storage": [], "quota_sources": []})
    return result


def _validate_args(args: argparse.Namespace) -> None:
    if not PLUGIN_ID_RE.fullmatch(args.plugin_id):
        raise ValueError("plugin-id must match the manifest ID pattern")
    if not PROFILE_ID_RE.fullmatch(args.profile_id):
        raise ValueError("profile-id must match ^[a-z][a-z0-9_-]{0,63}$")
    if not SEMVER_RE.fullmatch(args.version):
        raise ValueError("version must be semantic X.Y.Z without leading zeroes")
    try:
        Version(args.version)
        SpecifierSet(args.requires_app)
    except (InvalidVersion, InvalidSpecifier) as exc:
        raise ValueError("requires-app must be a valid supported version range") from exc
    if not args.name.strip() or not args.publisher.strip() or not args.description.strip():
        raise ValueError("name, publisher, and description are required")


def _full_profile(profile_id: str, name: str) -> dict:
    profile = build_profile(profile_id, name, 2)
    profile.update({"description": "Fill only verified public provider information.",
        "metadata": {"maintainer": "", "documentation_url": None, "support_url": None},
        "site": {"public_name": "", "region": "", "access_note": "", "documentation_url": None},
        "scheduler_hints": {"queue_notes": "", "account_notes": "", "partitions": []},
        "software": {"module_paths": [], "setup_notes": ""},
        "storage": [{"id": kind, "label": kind.replace("-", " ").title(), "kind": kind,
            "enabled": True, "path_template": "", "access_context": "unknown",
            "policy": {"backup": None, "retention_days": None}}
            for kind in ("home", "scratch", "project", "custom", "node-local")],
        "quota_sources": [{"id": "example-quota", "enabled": False, "backend_id": None,
            "command_template": None, "scope": "unknown"}]})
    return profile


<<<<<<< HEAD
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
=======
def create_package(args: argparse.Namespace) -> Path:
    _validate_args(args)
    target = args.output_dir.resolve()
    if "plugins" in {part.casefold() for part in target.parts}:
        raise ValueError("scaffolder refuses to write inside published plugin directories")
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise FileExistsError(f"refusing non-empty output directory: {target}")
    target.mkdir(parents=True, exist_ok=True)
    profile = build_profile(args.profile_id, args.name) if args.template == "minimal" else _full_profile(args.profile_id, args.name)
    profile_bytes = (json.dumps(profile, indent=2) + "\n").encode()
    readme_bytes = (f"# {args.name}\n\n{args.description.strip()}\n\n"
                    "Fill only verified public values. Quota is disabled by default.\n").encode()
    (target / "cluster-profile.json").write_bytes(profile_bytes)
    (target / "README.md").write_bytes(readme_bytes)
    manifest = {"schema_version": 1, "plugin_api": 1, "id": args.plugin_id,
        "name": args.name.strip(), "version": args.version, "publisher": args.publisher.strip(),
        "license": "MIT", "description": args.description.strip(),
        "requires_app": args.requires_app.strip(), "capabilities": ["cluster-profile"],
        "entrypoints": {"cluster_profiles": ["cluster-profile.json"]}, "files": []}
    for rel, role in (("cluster-profile.json", "cluster-profile"), ("README.md", "documentation")):
        data = (target / rel).read_bytes()
        manifest["files"].append({"path": rel, "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data), "role": role})
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    problems: list[str] = []
    validate_against_schema(
        manifest, Path(__file__).resolve().parents[1] / "schema" / "manifest.schema.json",
        "generated manifest", problems,
    )
    problems.extend(f"generated profile: {problem}" for problem in validate_cluster_profile(profile))
    if problems:
        raise ValueError("generated package is invalid: " + "; ".join(problems))
    return target
>>>>>>> origin/main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
<<<<<<< HEAD
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
=======
    parser.add_argument("--plugin-id", required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--requires-app", required=True)
    parser.add_argument("--publisher", default="HPC Client GUI contributor")
    parser.add_argument("--description", default="Declarative cluster-profile plugin.")
    parser.add_argument("--template", choices=("minimal", "full"), default="minimal")
    parser.add_argument("--output-dir", type=Path, required=True)
    create_package(parser.parse_args())
>>>>>>> origin/main
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
