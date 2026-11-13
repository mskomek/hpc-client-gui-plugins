# W65 OpenFOAM Linter 0.2.0-w65r8 review candidate

Status: REVIEW CANDIDATE — not install-validated, not published, and not wired into the current host loader.

This version preserves the prior plugin package files and adds the audited W65 round-8 Python/JSON source snapshot under engine/hpc_gui/. The existing manifest entrypoint remains unchanged and still points to the inherited legacy engine. In the W65 source, openfoam_studio/host_adapter.py explicitly describes its contribution data as unregistered. Treat the added tree as review material until host-loader integration and the full package install/upgrade/rollback/uninstall matrix pass.

Source provenance and per-file SHA-256 values are in W65_SOURCE_BINDINGS.json. W65 audit and confirm verdicts were PASS; the overall W65 release verdict remains PARTIAL because v2312 runtime, VM package lifecycle, GUI receipts, and live lab checks are incomplete.
