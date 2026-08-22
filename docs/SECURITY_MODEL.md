# Security Model

## What Plugin API v1 is

A declarative data distribution system for HPC Client GUI. Plugins contain
JSON/text/Markdown only — no Python, no binaries, no hooks, nothing that the
application executes as plugin code.

## Guarantees in v1

1. **Official registry only.** The application supports exactly one registry
   URL (this repository). Third-party custom registries are not exposed in
   normal UI.
2. **Install never executes plugin content.** Installing downloads, verifies,
   and stages files. No plugin-supplied command runs at install time.
3. **Full validation before activation:** safe relative paths (no `..`,
   absolute paths, backslashes, URLs), JSON Schema conformance, app/API
   compatibility, per-file size and SHA-256 verification.
4. **Hash mismatch is a hard failure.** Any integrity error aborts install.
5. **Plugin actions are user-initiated only.** Cluster command templates are
   used solely inside existing application workflows after explicit user
   action.
6. **Failed network/plugin operations must not crash the app** and network
   work stays off the GUI thread.

## Explicit non-guarantees

- The hash chain (`registry -> manifest -> files`) proves integrity against
  this repository. It is **not** publisher-signature security: a compromised
  official repository could rewrite both content and hashes. A signed
  registry with an application-embedded public key is a planned hardening
  step.
- Cluster profiles contain remote scheduler/status command templates. These
  are privileged declarative data: review them like you would review shell
  commands before running them on a cluster you care about.

## Reporting

See [SECURITY.md](../SECURITY.md) at the repository root.
