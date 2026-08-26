#!/usr/bin/env python3
"""Convenience launcher for the ANSYS Script & Journal Linter CLI.

Resolves the newest bundled engine under ``plugins/ansys-lint/<version>/engine``
and runs its argparse CLI. The linter itself is pure standard-library Python
and runs fully offline.

Examples:
    python scripts/ansys-journal-lint.py path/to/file.jou
    python scripts/ansys-journal-lint.py folder --version 25.2 --target linux --mode batch
    python scripts/ansys-journal-lint.py file.dat --dialect mapdl --format json
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _engine_dir() -> Path | None:
    base = REPO_ROOT / "plugins" / "ansys-lint"
    candidates = sorted(base.glob("*/engine"))
    return candidates[-1] if candidates else None


def main() -> int:
    engine = _engine_dir()
    if engine is None:
        print("error: no plugins/ansys-lint/*/engine directory found", file=sys.stderr)
        return 3
    # The engine ships inside an immutable plugin version directory; never
    # let import machinery drop __pycache__ artifacts there.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(engine))
    try:
        from ansys_lint.cli import main as cli_main
    except ImportError as exc:
        print(f"error: cannot import the linter engine: {exc}", file=sys.stderr)
        return 3
    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
