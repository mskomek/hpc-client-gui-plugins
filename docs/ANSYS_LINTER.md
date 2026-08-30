# ANSYS Script & Journal Linter

An **unofficial**, offline linter for the broader family of Ansys script,
journal, replay, session, state and batch-command formats. It ships as the
optional plugin `org.hpcclient.ansyslint` (Plugin API v2, capability
`linter-tool`) for HPC Client GUI.

> **Unofficial notice.** This plugin is not affiliated with, endorsed by,
> or produced by Ansys, Inc. It does not replace the official Ansys
> documentation. Heuristic warnings may require manual verification.
> Always verify scripts against the *exact* Ansys release installed on your
> cluster.

## Supported products and file types

| Product | Dialect / files | Coverage class |
|---|---|---|
| Ansys Fluent | `.jou` journals, TUI commands, Scheme expressions, TUI inside Workbench `SendCommand` | structural + catalog-backed (partial catalog) + heuristic |
| Mechanical APDL | `.dat`, `.inp`, `.mac`, APDL-oriented `.log` (`Jobname.log` replays), embedded APDL snippets | structural + catalog-backed (partial) + heuristic; user-selectable strictness |
| Workbench | `.wbjn`, Workbench-oriented `.py`; nested `SendCommand()` extraction | outer Python: structural/exact; nested dialects routed to their parsers with outer-file line/column mapping |
| CFX-Pre | `.pre` sessions, `.ccl` state | structural (object balance, CEL parens) + heuristic portability |
| CFD-Post | `.cse` sessions, `.cst` state | structural + heuristic |
| TurboGrid | `.tse` sessions, `.tst` state | structural incl. required final `>quit` in batch + heuristic |
| ICEM CFD | `.rpl` replay scripts (Tcl variation) | structural Tcl scanning + documented `ic_*` subset; undocumented `ic_*` flagged honestly |
| System Coupling | `-R run.py` scripts | Python AST + command-name subset + allocation-fraction arithmetic |
| Mechanical | `.py`, legacy `.js`/`.vbs`/`.mcr`, embedded APDL command snippets | structural + signature detection; no full API validation |
| DesignModeler | `.js` (JScript, `agb.*`) | structural JScript checks + header/version heuristics |
| Ansys Meshing | content via Workbench `SendCommand` (container-aware) | container detection before interpretation; explicit `Language=` respected |
| SpaceClaim / Discovery | `.scscript`, `.py` | Python syntax + product signatures + interactive-selection warnings |
| Electronics Desktop (HFSS/Maxwell/Twin Builder) | `.py`, legacy `.vbs` | detection first; COM/GUI-dependency warnings; no fabricated API diagnostics |
| Aqwa | embedded JScript via `SendCommand` | structural + portability only |
| Motion | `.dfjnl` (XML journal) | XML well-formedness (exact), structural operation/file-reference notes |

Ambiguous extensions (`.py`, `.dat`, `.log`, `.js`, `.inp`, `.txt`) are
**never** classified by extension alone. A confidence-based detector combines
extension, header comments, known commands/imports/object names, declared
Ansys versions, Workbench container context and an optional surrounding
launch command. When confidence is low you are asked to pick the
product/dialect instead of receiving floods of false diagnostics.

## Exact vs heuristic validation - honest coverage

Every diagnostic carries `is_heuristic` plus a confidence level:

- **Exact / structural** (`is_heuristic = false`): Fluent `set-tui-version`
  handling, shell escapes, Scheme paren balance, output-after-solve
  structure, bare `/exit` prompt risk, MAPDL block pairing
  (`*DO/*ENDDO`, `*IF/*ENDIF`, `*CREATE/*END`, `*PYTHON/*ENDPY`),
  processor tracking, embedded-Python syntax, CCL object balance and stray
  `END`, CEL paren balance, TurboGrid batch `>quit` requirement, ICEM Tcl
  structure, System Coupling literal fraction arithmetic, Motion XML
  well-formedness, case-mismatched file references.
- **Catalog-backed**: command availability for the selected version pack
  (Fluent TUI packs: 24.2, 25.1, 25.2, 26.1; MAPDL command catalog;
  System Coupling command subset). Catalogs ship **partial** by design:
  only entries whose menu path and availability are well established are
  included. Unknown commands never produce errors - only low-confidence
  notes pointing at the official reference.
- **Heuristic recommendations** (`is_heuristic = true`): GUI operations in
  headless runs, overwrite handling without `/file/confirm-overwrite`,
  missing solve/output suggestions, graphics-in-batch notes, Windows path /
  `%ENV%` portability findings, absolute install paths, unquoted spaces,
  COM/desktop dependencies, interactive-selection dependencies.

The linter works fully offline at runtime. Documentation links are opened
only when you explicitly click them.

## Supported Ansys releases

Default target: **2025 R2 (`25.2`)** - the current TRUBA Fluent environment.

Fluent version packs: `24.2` (2024 R2), `25.1` (2025 R1), `25.2` (2025 R2),
`26.1` (2026 R1). A journal that declares `/file/set-tui-version 24.2` is
validated against the 24.2 pack - never silently against the newest one.
Other products are covered against 2025 R2 references; rules derived from
older pages (e.g. CFD-Post actions from 2025 R1, Meshing container from
2025 R1) are labelled with their release in [sources.md](../plugins/ansys-lint/0.1.0/docs/sources.md).

Never validated against a newer catalog than the file declares: if a file
declares an older version, later-introduced commands produce
`FLUENT_TUI_ADDED_LATER` warnings.

## Installation

1. Open HPC Client GUI >= 1.5.0 -> **Plugins** (top-right).
2. Find "ANSYS Script & Journal Linter" in **Discover**.
3. Install. Every payload byte is SHA-256-verified during download; the
   engine activates only after full verification.
4. The installed plugin card shows an **Open tool** button hosting the
   linter page. Nothing executes at install time; the engine loads lazily.

## GUI usage

The linter page offers:

- file selection and optional folder scan;
- automatic product/dialect detection with manual override combo;
- Ansys version selector (24.2 / 25.1 / 25.2 / 26.1);
- execution mode selector (batch / headless / interactive);
- target OS selector (Linux / Windows);
- MAPDL strictness selector (lenient / strict);
- launch-command field (e.g. `runwb2 -B -R job.wbjn`) for extra context;
- severity filters; grouping by file; line/column display;
- per-diagnostic source link button (opens the official Ansys page);
- copy diagnostic; export as JSON or text;
- a concise error/warning/info summary.

Linting runs on a worker thread; the GUI stays responsive.

## CLI usage

From the plugins repository checkout:

```bash
python scripts/ansys-journal-lint.py path/to/file.jou
python scripts/ansys-journal-lint.py folder --version 25.2 --target linux --mode batch
python scripts/ansys-journal-lint.py file.wbjn --format json
python scripts/ansys-journal-lint.py file.dat --dialect mapdl --strictness strict
python scripts/ansys-journal-lint.py --list-dialects
```

Exit codes:

| Code | Meaning |
|---|---|
| 0 | success - no blocking findings |
| 1 | findings at/above `--fail-on` threshold (default: error) |
| 2 | unsupported or undetected format |
| 3 | internal failure |

JSON output is stable and machine-readable (CI friendly): tool/version
metadata, per-file detection info and diagnostics, and aggregate summary.

## Diagnostic severity model

- `error` - definite problems: unbalanced blocks, unterminated CCL objects,
  removed commands, invalid allocations, malformed XML, broken Python/Tcl
  syntax.
- `warning` - likely trouble needing attention: GUI-in-batch, unsafe
  overwrite handling, Windows paths under Linux targets, shell execution.
- `info` - recommendations and honest uncertainty notes: missing version
  declarations, unknown-but-maybe-valid commands, low-confidence hints.

Confidence (`high` / `medium` / `low`) and `is_heuristic` accompany every
diagnostic; source-backed ones include `source_id`, `source_url` and
`source_title`.

## Limitations

- The Fluent TUI catalog ships 100+ high-confidence commands covering the
  common file/solve/monitor/report/parameter/viscous families (validated
  against real production journals). Unknown commands yield informational
  notes, never errors. Bare prompt-answer lines are replay content and are
  not treated as commands at all.
- No MAPDL/Mechanical/SpaceClaim/AEDT/Aqwa API validation is claimed.
- CCL object-level cross-product validity (CFD-Post objects in TurboGrid)
  is not checked.
- Motion validation is structural unless a complete operation schema is
  available.
- Generic Python syntax checks do not prove any product API call valid.

Every heuristic diagnostic says so explicitly, both in the JSON payload and
in the GUI tooltip ("heuristic recommendation - verify manually").

## Official source registry

Provenance lives in
`plugins/ansys-lint/<version>/engine/ansys_lint/data/sources.json` and the
human-readable copy in [sources.md](../plugins/ansys-lint/0.1.0/docs/sources.md). Each entry stores the
minimum needed: identifier, official URL, title, product, release and a
one-line original-language note written by this project. No manual text is
copied from Ansys documentation.

## Contributing a new version pack or dialect

Adding a Fluent release (e.g. 27.0):

1. Add `"27.0"` to `engine/ansys_lint/data/fluent_versions.json`
   (`order`, `versions` with its `set_tui_version_value`).
2. Add/adjust catalog deltas in `fluent_tui.json` using `introduced` /
   `removed` / `replaced_by` fields - parser logic never changes.
3. Reference the official migration-manual URL in `data/sources.json`.
4. Add tests mirroring `tests/test_ansys_lint_engine.py`.

Adding a new dialect:

1. Implement `lint(text, options, *, file_path, mapper=None)` in
   `engine/ansys_lint/dialects/`.
2. Register it in `dialects/__init__.py` (`LINTERS`, `DIALECT_LABELS`).
3. Add detector evidence to `detection.py` (extension base + signature
   boosts). Keep ambiguous formats below the auto-threshold until
   signatures justify them.
4. Extend fixtures/golden tests and this document.
