#!/usr/bin/env python3
"""Developer convenience: refresh payload hashes in manifests, then manifest
hashes in the registry.

Run this after editing payload files under a plugin version directory. The
script never changes plugin versions; it only recomputes:

    file sha256/size  ->  manifest.json files[]
    manifest sha256   ->  registry.json plugins[].manifest_sha256

Per repository policy, published version directories are immutable once
merged to `main`. Prefer creating a new version directory instead of
refreshing hashes of an already-published version.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_registry import REPO_ROOT, load_json, sha256_of  # noqa: E402


def write_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def refresh() -> int:
    changed_manifests = 0
    registry_path = REPO_ROOT / "registry.json"
    if not registry_path.is_file():
        print("registry.json not found", file=sys.stderr)
        return 1

    registry = load_json(registry_path)
    for entry in registry.get("plugins", []):
        manifest_path = REPO_ROOT / entry["manifest_path"]
        if not manifest_path.is_file():
            print(f"SKIP {entry['id']}@{entry['version']}: manifest missing")
            continue

        manifest = load_json(manifest_path)
        manifest_changed = False
        for file_entry in manifest.get("files", []):
            payload_path = manifest_path.parent / file_entry["path"]
            if not payload_path.is_file():
                print(f"ERROR {entry['id']}: payload '{file_entry['path']}' missing", file=sys.stderr)
                return 1
            new_hash = sha256_of(payload_path)
            new_size = payload_path.stat().st_size
            if new_hash != file_entry["sha256"] or new_size != file_entry["size"]:
                print(
                    f"UPDATE {manifest_path.relative_to(REPO_ROOT)}::{file_entry['path']} "
                    f"(sha256 {file_entry['sha256'][:12]}... -> {new_hash[:12]}..., "
                    f"size {file_entry['size']} -> {new_size})"
                )
                file_entry["sha256"] = new_hash
                file_entry["size"] = new_size
                manifest_changed = True

        if manifest_changed:
            write_json(manifest_path, manifest)
            changed_manifests += 1

        new_manifest_hash = sha256_of(manifest_path)
        if new_manifest_hash != entry["manifest_sha256"]:
            print(
                f"UPDATE registry entry {entry['id']}@{entry['version']} manifest_sha256 -> {new_manifest_hash}"
            )
            entry["manifest_sha256"] = new_manifest_hash

    write_json(registry_path, registry)
    print(f"Done. Manifests rewritten: {changed_manifests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(refresh())
