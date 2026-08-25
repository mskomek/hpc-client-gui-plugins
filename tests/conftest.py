import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _add_ansys_lint_engine() -> None:
    """Expose the bundled linter engine as the importable package
    ``ansys_lint`` for the whole test session."""
    engines = sorted((SCRIPTS_DIR.parent / "plugins" / "ansys-lint").glob("*/engine"))
    if engines:
        sys.path.insert(0, str(engines[-1]))


_add_ansys_lint_engine()
