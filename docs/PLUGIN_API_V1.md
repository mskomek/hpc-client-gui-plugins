# Plugin API v1

Plugin API v1 is **declarative**. A plugin is a set of data files described by
a `manifest.json`, published under a stable version directory in this
repository and indexed by the top-level `registry.json`.

> v1 remains fully supported and unchanged. Plugin API v2 adds one
> opt-in capability for hash-verified linter engines; see
> [PLUGIN_API_V2.md](PLUGIN_API_V2.md).

## What v1 allows

- JSON metadata (`manifest.json`, `registry.json`)
- JSON cluster profiles
- JSON lint rules and lint indexes
- JSON template indexes and textual template content
- Markdown/text documentation

Allowed payload file extensions: `.json`, `.md`, `.txt`, `.tpl`.

## What v1 must never contain

- Python modules or any importable code
- DLLs/shared libraries or executables
- shell/PowerShell hooks
- dynamically imported classes
- `eval`/`exec` content

The validator rejects executable-looking extensions and unknown payload roles.
Roles are limited to: `cluster-profile`, `lint-index`, `lint-rules`,
`template-index`, `template-content`, `documentation`.

## Identity and versioning

- Plugin IDs are stable reverse-domain-like strings
  (`org.hpcclient.truba`, `org.hpcclient.fluent`). Never derive identity from
  a display name.
- Plugin versions are semantic versions (`1.0.0`, `0.1.0`).
- `plugin_api` is the integer `1`. Schema files use `"schema_version": 1`.
  These two version concepts change independently.
- Capabilities vocabulary: `cluster-profile`, `lint-rules`, `job-template`,
  `application-tools`.
- Registry entries may declare a `capabilities` array. For plugins that
  combine capabilities (for example lint rules plus a job template), the
  array is authoritative; the single legacy `type` field remains for display
  compatibility and must not contradict the manifest. CI verifies that the
  registry entry and `manifest.json` agree on id, version, name, publisher,
  plugin API version, `requires_app`, capabilities, paths, and hashes.

## Compatibility

`requires_app` uses the small version-range subset understood by HPC Client
GUI: an optional operator `>=`, `<=`, `==`, or `~=` followed by a semantic
version, e.g. `>=1.4.0`. Unsupported operators fail validation.

## Cluster profiles are privileged declarative data

Cluster-profile payloads contain remote command templates that the desktop
application eventually runs over SSH — but only through existing,
user-initiated workflows. For v1:

- only the official registry is supported;
- the plugin detail UI shows that a plugin supplies cluster commands;
- no third-party custom registries are exposed in normal UI;
- no plugin command ever runs at install time;
- command fields must quote interpolated values safely
  (`cd -- {script_dir_q}` style placeholders).

## Immutability of published versions

Once a version directory has been merged to `main`, treat it as immutable.
Fix problems by publishing a new version directory and registry entry; never
mutate published hashes in place. The application mirrors this on the client:
an already-installed version is reused only when its verified contents match
the incoming manifest byte-for-byte; conflicting or corrupt same-version
content produces an integrity error and the previously active version stays
active. Updates activate only after full verification, keep the previous
version directory for rollback, and write the active-version pointer through
atomic file replacement.

Note that these guarantees are best-effort filesystem semantics (same-volume
rename, verified reuse), not transactional journaling: a hard power loss
mid-install can still leave staging files behind; they are cleaned up on the
next install attempt and never affect the active version.
