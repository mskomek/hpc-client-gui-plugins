"""OpenFOAM Linter plugin identity + facade (W65 LINT-013). Version 0.2.0-w65r1."""

from __future__ import annotations

PLUGIN_ID = "openfoam-linter"
PLUGIN_VERSION = "0.2.0-w65r1"
PLUGIN_BASE = "0.1.0"
# Preserved 0.1.0 rule-ID prefixes; new W65 rules extend the same families.
RULE_FAMILIES = ("OF-DICT", "OF-CASE", "OF-CTRL", "OF-SOLVER", "OF-BC",
                 "OF-MESH", "OF-CROSS", "OF-PAR", "OF-HPC", "OF-SEC")
