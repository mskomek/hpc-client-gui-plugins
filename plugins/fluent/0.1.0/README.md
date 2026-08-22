# ANSYS Fluent Journal lint plugin

Declarative, static best-effort checks for ANSYS Fluent journal files
(`*.jou`), provided as Plugin API v1 `lint-rules`.

## Important limitations

- This linter is **static and best-effort**: it never executes Fluent and it
  cannot guarantee that a journal will run.
- Rules are deliberately conservative and curated; this is **not** a complete
  TUI validity database and makes no such claim.
- Always validate important production journals against your actual Fluent
  installation.

## Current rules (0.1.0)

| ID | Severity | When | Summary |
|---|---|---|---|
| FLUENT001 | warning | always | Journal does not declare a Fluent TUI version (`/file/set-tui-version`). |
| FLUENT002 | warning | target 25.2 | Declared journal TUI version differs from the selected 25.2 target. |
| FLUENT003 | info | target 25.2 | `/file/set-tui-version` appears after substantive TUI commands (conservative: only `/solve` is considered). |
| FLUENT010 | warning | remote platform is Linux | Windows-style absolute path (`C:\...`, `D:/...`) in a Linux/HPC execution context. |
| FLUENT011 | info | always | Absolute path may reduce portability (not necessarily wrong). |

## Future categories (documented, not shipped)

- **Confirmation prompts**: unanswered confirmation requests can stop journal
  playback. A rule pack will only cover commands verified in official
  documentation with a curated mapping — no speculative rules yet.
- **Execution order** (e.g. iterate before case read): a journal can receive
  its case from the Fluent CLI externally, so such checks stay informational
  unless explicit context says otherwise.
- **Modernization hints** (Python journaling / `-topy`, Fluent 2024 R2+): an
  opt-in informational category planned for a later version.

## Sources

See [docs/sources.md](docs/sources.md) for the official documentation links
these rules are based on.

## Installation

Install from inside HPC Client GUI via the Plugin Manager. Installing never
executes any rule content or Fluent itself.
