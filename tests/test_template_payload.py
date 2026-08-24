"""`.tpl` template payload acceptance and routing tests.

Covers the Fluent-style `.tpl` workflow end to end at the registry level:
a valid `.tpl`-based job-template plugin is accepted, and an undeclared
template file inside an immutable version directory is rejected.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from validate_registry import REPO_ROOT, validate_repository
from test_registry import build_registry, run_validator


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _add_tpl_plugin(root: Path, *, undeclared_extra: bool = False) -> dict:
    """Create a self-consistent job-template plugin whose content is .tpl."""
    base = "plugins/tpltest/1.0.0"
    version_dir = root / base
    version_dir.mkdir(parents=True)

    tpl_body = (
        "#!/bin/bash\n"
        "#SBATCH --partition={{partition}}\n"
        "#SBATCH --nodes=1\n"
        "#SBATCH --ntasks={{ntasks}}\n"
        "gmx mdrun -s {{input_tpr}}\n"
    ).encode("utf-8")
    (version_dir / "job.slurm.tpl").write_bytes(tpl_body)

    index = {
        "schema_version": 1,
        "name": "TPL test templates",
        "templates": [
            {
                "id": "tpl-basic",
                "name": "TPL basic",
                "scheduler": "slurm",
                "content_path": "job.slurm.tpl",
                "sha256": sha256_bytes(tpl_body),
            }
        ],
    }
    index_bytes = json.dumps(index, indent=2).encode("utf-8")
    (version_dir / "index.json").write_bytes(index_bytes)

    if undeclared_extra:
        (version_dir / "extra.slurm.tpl").write_bytes(
            b"#!/bin/bash\n# never declared in any manifest\n"
        )

    files = [
        {
            "path": "index.json",
            "role": "template-index",
            "size": len(index_bytes),
            "sha256": sha256_bytes(index_bytes),
        },
        {
            "path": "job.slurm.tpl",
            "role": "template-content",
            "size": len(tpl_body),
            "sha256": sha256_bytes(tpl_body),
        },
    ]
    manifest = {
        "schema_version": 1,
        "plugin_api": 1,
        "id": "org.hpcclient.tpltest",
        "name": "TPL Test Plugin",
        "version": "1.0.0",
        "publisher": "HPC Client GUI",
        "license": "MIT",
        "description": "A .tpl-based test plugin.",
        "requires_app": ">=1.4.0",
        "capabilities": ["job-template"],
        "entrypoints": {"template_index": "index.json"},
        "files": files,
    }
    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
    (version_dir / "manifest.json").write_bytes(manifest_bytes)

    return {
        "id": "org.hpcclient.tpltest",
        "name": "TPL Test Plugin",
        "version": "1.0.0",
        "plugin_api": 1,
        "type": "job-template",
        "description": "A .tpl-based test plugin.",
        "publisher": "HPC Client GUI",
        "requires_app": ">=1.4.0",
        "manifest_path": f"{base}/manifest.json",
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "official": True,
    }


def test_real_fluent_tpl_plugin_is_accepted():
    """The published Fluent 0.2.0 plugin uses a routed .tpl file."""
    errors, _warnings = validate_repository(REPO_ROOT)
    assert errors == []
    manifest = json.loads(
        (REPO_ROOT / "plugins/fluent/0.2.0/manifest.json").read_text(encoding="utf-8")
    )
    tpl_entries = [f for f in manifest["files"] if f["path"].endswith(".tpl")]
    assert len(tpl_entries) == 1
    assert tpl_entries[0]["role"] == "template-content"


def test_synthetic_declared_tpl_plugin_is_accepted(tmp_path):
    entry = _add_tpl_plugin(tmp_path)
    build_registry(tmp_path, [entry])
    errors, _warnings = run_validator(tmp_path)
    assert errors == []


def test_unreported_template_file_is_rejected(tmp_path):
    entry = _add_tpl_plugin(tmp_path, undeclared_extra=True)
    build_registry(tmp_path, [entry])
    errors, _warnings = run_validator(tmp_path)
    joined = "\n".join(errors)
    assert errors, "expected validator failure"
    assert "undeclared extra file" in joined
    assert "extra.slurm.tpl" in joined


def test_installed_distribution_ships_no_payload_files():
    """When installed (`pip install -e .`), the distribution must contain no
    plugins/, schema/, or registry payload files."""
    try:
        import importlib.metadata as metadata
    except ImportError:  # pragma: no cover
        return
    try:
        dist = metadata.distribution("hpc-client-gui-plugins")
    except metadata.PackageNotFoundError:
        return  # not installed here; CI runs this after `pip install -e ".[dev]"`
    recorded = (dist.read_text("RECORD") or "").splitlines()
    names = {line.split(",")[0] for line in recorded if line.strip()}
    bad = [
        name
        for name in names
        if name.startswith(("plugins/", "schema/")) or name == "registry.json"
    ]
    assert bad == []
