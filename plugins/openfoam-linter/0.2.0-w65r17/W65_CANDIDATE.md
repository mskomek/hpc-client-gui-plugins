# W65 OpenFOAM Linter 0.2.0-w65r17 review candidate

Status: REVIEW CANDIDATE — not install-validated, not published, and not wired into the current host loader.

This snapshot contains the W65 round-17 source tree, committed as f4470d7b0ac007ae57bcd72aade3f817ae8cd05e on branch wave-auto. The existing package files and manifest entrypoint are preserved; the inherited entrypoint continues to point to the legacy engine. Treat the added `engine/hpc_gui/` source as review material until host-loader integration and the full install, upgrade, rollback, and uninstall matrix pass.

`W65_SOURCE_BINDINGS.json` binds each included source file to the committed worktree and records the loop audit and confirm receipts under `artifacts/loop_audit/W65/`. W65 audit and confirm both passed. Product release remains PARTIAL / BLOCKED_ENV because the v2312 runtime, VM package lifecycle, GUI receipts, and live lab checks are incomplete.
