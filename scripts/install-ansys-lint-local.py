#!/usr/bin/env python3
"""Install org.hpcclient.ansyslint from THIS local checkout into the real
HPC Client GUI plugin storage, so the Plugin Manager (run from application
source) shows it as Installed without waiting for a registry push.

The install uses the application's own installer: every payload byte is
verified against the local manifest exactly as an official download would
be. Nothing is pushed anywhere.

Usage:
    python scripts/install-ansys-lint-local.py [--app-src <TrubaGUI/src>]
                                               [--root <storage root>]
                                               [--remove]

Defaults:
    --app-src  D:\\Projeler\\TrubaGUI\\src  (sibling checkout, must be on
               application v1.5.0+ because the plugin requires >=1.5.0)
    --root     the application's default plugin storage (same place the
               GUI reads), pass a temp path for sandbox testing

After installing, launch the app from source and open:
    Plugins -> Installed -> ANSYS Script & Journal Linter -> Open tool
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "plugins" / "ansys-lint" / "0.1.0"
DEFAULT_APP_SRC = Path(r"D:\Projeler\TrubaGUI\src")


def _bootstrap_app_src(app_src: Path) -> None:
    if not (app_src / "hpc_gui").is_dir():
        raise SystemExit(f"error: hpc_gui package not found under {app_src}")
    sys.path.insert(0, str(app_src))


def _local_fetcher(repo_root: Path):
    raw_base = "https://raw.githubusercontent.com/mskomek/hpc-client-gui-plugins/main/"

    def fetch(url: str, max_bytes: int) -> bytes:
        assert url.startswith(raw_base), url
        payload = (repo_root / url[len(raw_base):]).read_bytes()
        if len(payload) > max_bytes:
            raise OSError("payload exceeds size limit")
        return payload

    return fetch


def _build_entry(manifest_path: Path) -> tuple[dict, dict]:
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    entry = {
        "id": manifest["id"],
        "name": manifest["name"],
        "version": manifest["version"],
        "plugin_api": manifest["plugin_api"],
        "type": "linter-tool",
        "description": manifest["description"],
        "publisher": manifest["publisher"],
        "requires_app": manifest["requires_app"],
        "manifest_path": f"plugins/ansys-lint/{manifest['version']}/manifest.json",
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "official": True,
        "capabilities": manifest["capabilities"],
    }
    # The fetcher resolves paths relative to this repository root, so the
    # registry-style manifest path maps onto plugins/ansys-lint/<version>/.
    return entry, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--app-src", type=Path, default=DEFAULT_APP_SRC)
    parser.add_argument("--root", type=Path, default=None,
                        help="override plugin storage root (sandbox testing)")
    parser.add_argument("--remove", action="store_true",
                        help="remove the installed plugin instead")
    args = parser.parse_args()

    _bootstrap_app_src(args.app_src)
    import hpc_gui
    from hpc_gui.plugins.state import remove_plugin

    print(f"application version: {hpc_gui.__version__}")
    if args.remove:
        removed = remove_plugin("org.hpcclient.ansyslint", root=args.root)
        print("removed:", removed)
        return 0

    from hpc_gui.plugins.installer import install_plugin_from_registry
    from hpc_gui.plugins.loader import load_installed_plugins

    entry, manifest = _build_entry(PLUGIN_DIR / "manifest.json")
    result = install_plugin_from_registry(
        entry,
        root=args.root,
        app_version=hpc_gui.__version__,
        fetcher=_local_fetcher(REPO_ROOT),
    )
    print(
        f"installed {result.installed.manifest.id}@"
        f"{result.installed.manifest.version} (activated={result.activated})"
    )

    loaded = load_installed_plugins(root=args.root, app_version=hpc_gui.__version__)
    match = next(
        (p for p in loaded.plugins if p.manifest.id == "org.hpcclient.ansyslint"),
        None,
    )
    if match is None or not match.linter_engine:
        raise SystemExit("error: installed plugin did not load with a linter engine")
    print("loader OK; engine module recorded:", match.linter_engine["module"])
    print()
    print("Next steps:")
    print("  cd D:\\Projeler\\TrubaGUI-develop-work")
    print('  $env:PYTHONPATH = "src"; python -m hpc_gui')
    print("  Plugins -> Installed -> ANSYS Script & Journal Linter -> Open tool")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
