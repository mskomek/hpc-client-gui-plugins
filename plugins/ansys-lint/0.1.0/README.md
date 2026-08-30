# ANSYS Script & Journal Linter

Unofficial offline linter for Ansys script/journal formats, shipped as a
Plugin API v2 `linter-tool` for HPC Client GUI >= 1.5.0.

- Products: Fluent journals/TUI/Scheme, Workbench `.wbjn` with nested
  `SendCommand`, MAPDL inputs, CFX-Pre/CFD-Post/TurboGrid CCL sessions and
  states, ICEM `.rpl` replays, System Coupling `-R` scripts, Mechanical,
  DesignModeler, Meshing (via container), SpaceClaim/Discovery, AEDT,
  Aqwa (embedded), Motion `.dfjnl`.
- Fluent version packs: 24.2 / 25.1 / **25.2 (default)** / 26.1.
- Offline at runtime; documentation links open only on user request.
- Diagnostics carry stable codes, severities, confidence levels,
  `is_heuristic` flags and official source links where catalog-backed.

Full documentation: [ANSYS_LINTER.md](../../../../docs/ANSYS_LINTER.md)
(products, exact-vs-heuristic coverage, GUI/CLI usage, limitations,
contributing new version packs).

This plugin is not affiliated with or endorsed by ANSYS, Inc. It does not
replace the official Ansys documentation; verify scripts against your
installed release.
