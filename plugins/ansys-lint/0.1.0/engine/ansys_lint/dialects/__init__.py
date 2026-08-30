"""Versioned dialect registry.

Every supported dialect registers one lint entry point here. Adding a new
dialect or product means adding an entry - parser dispatch logic elsewhere
never changes. Version packs live beside each parser under ``data/``.
"""

from __future__ import annotations

from functools import partial
from typing import Callable

from . import (
    aedt,
    aqwa,
    ccl,
    designmodeler,
    fluent,
    icem,
    mapdl,
    mechanical,
    motion,
    spaceclaim,
    sysc,
    workbench,
)

# dialect key -> display label
DIALECT_LABELS: dict[str, str] = {
    "fluent": "Ansys Fluent journal / TUI / Scheme",
    "mapdl": "Mechanical APDL batch input",
    "workbench": "Ansys Workbench journal (Python)",
    "cfx-pre-session": "CFX-Pre session (.pre)",
    "ccl": "CCL state (.ccl)",
    "cfd-post-session": "CFD-Post session (.cse)",
    "cfd-post-state": "CFD-Post state (.cst)",
    "turbo-grid-session": "TurboGrid session (.tse)",
    "turbo-grid-state": "TurboGrid state (.tst)",
    "icem-replay-tcl": "ICEM CFD replay script (.rpl)",
    "sysc-python": "System Coupling script (-R Python)",
    "mechanical-python": "Mechanical scripting (Python)",
    "mechanical-jscript": "Mechanical macro (legacy JScript)",
    "mechanical-vbscript": "Mechanical macro (legacy VBScript)",
    "designmodeler-jscript": "DesignModeler journal (JScript/agb.*)",
    "meshing-sendcommand": "Ansys Meshing SendCommand payload",
    "spaceclaim-python": "SpaceClaim / Discovery script",
    "aedt-python": "Electronics Desktop script (Python)",
    "aedt-vbscript": "Electronics Desktop script (VBScript)",
    "aqwa-jscript": "Aqwa journal (embedded JScript)",
    "motion-xml": "Motion journal (.dfjnl XML)",
}

# dialect key -> zero-arg factory returning a lint callable with the
# uniform signature (text, options, *, file_path, mapper=None).
LINTERS: dict[str, Callable[..., list]] = {
    "fluent": fluent.lint,
    "mapdl": mapdl.lint,
    "workbench": workbench.lint,
    "cfx-pre-session": partial(ccl.lint, product="cfx", kind="session"),
    "ccl": partial(ccl.lint, product="cfx", kind="state"),
    "cfd-post-session": partial(ccl.lint, product="cfd-post", kind="session"),
    "cfd-post-state": partial(ccl.lint, product="cfd-post", kind="state"),
    "turbo-grid-session": partial(ccl.lint, product="turbo-grid", kind="session"),
    "turbo-grid-state": partial(ccl.lint, product="turbo-grid", kind="state"),
    "icem-replay-tcl": icem.lint,
    "sysc-python": sysc.lint,
    "mechanical-python": partial(mechanical.lint, kind="python"),
    "mechanical-jscript": partial(mechanical.lint, kind="jscript"),
    "mechanical-vbscript": partial(mechanical.lint, kind="vbscript"),
    "designmodeler-jscript": designmodeler.lint,
    "meshing-sendcommand": partial(mechanical.lint, kind="jscript"),
    "spaceclaim-python": spaceclaim.lint,
    "aedt-python": partial(aedt.lint, kind="python"),
    "aedt-vbscript": partial(aedt.lint, kind="vbscript"),
    "aqwa-jscript": aqwa.lint,
    "motion-xml": motion.lint,
}

# Dialect keys that accept a CoordMapper for nested content remapping.
MAPPABLE_DIALECTS = frozenset({"fluent", "mapdl", "aqwa-jscript"})


def get_linter(dialect: str) -> Callable[..., list]:
    linter = LINTERS.get(dialect)
    if linter is None:
        raise KeyError(f"unknown dialect '{dialect}'")
    return linter


def known_dialects() -> tuple[str, ...]:
    return tuple(sorted(LINTERS))
