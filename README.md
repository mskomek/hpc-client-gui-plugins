# hpc-client-gui-plugins

> Official plugin registry for HPC Client GUI: cluster profiles, scheduler/application templates, and HPC lint rules.

This repository is the **official declarative plugin registry** for
[HPC Client GUI](https://github.com/mskomek/hpc-client-gui).

## What lives here

- `registry.json` — the machine-readable index of published plugins.
- `schema/` — JSON Schemas for every plugin payload type (Plugin API v1).
- `plugins/` — plugin payload directories (`manifest.json` + data files).
- `docs/` — Plugin API v1, registry protocol, security model, contributor guide.
- `scripts/` — developer validation/hash-refresh tooling (never shipped to clusters).

Plugins are **declarative data only**: JSON metadata, cluster profiles, lint
rules, templates, and Markdown documentation. No Python modules, binaries, or
hooks are distributed through this registry, and installing a plugin never
executes its content.

Initial plugin categories:

- `cluster-profile` — site/scheduler definitions such as TRUBA.
- `lint-rules` — HPC application linters such as ANSYS Fluent journal checks.
- `job-template` — reusable job submission templates.
- `application-tools` — application-specific helper definitions.

Installation happens from inside the HPC Client GUI Plugin Manager; no
server-side installation is needed on HPC clusters.

## Available plugins

| Plugin             | Capabilities                      | Latest version |
| ------------------ | --------------------------------- | -------------- |
| TRUBA              | Cluster profile                   | 1.0.0          |
| ANSYS Fluent Tools | Journal lint + Slurm job template | 0.2.0          |

HPC Client GUI is an independent community project. It is **not** an official
TÜBİTAK ULAKBİM/TRUBA or ANSYS, Inc. product, and these plugins are not
provided by those organizations.

## Version model

- **Immutable versions.** A published `plugins/<plugin>/<version>/` directory
  is never modified after release. Bug fixes and new features ship as a new
  version directory; old versions stay available for rollback.
- **Publishing a new version.** Create the new version directory with its
  `manifest.json`, add a registry entry pointing into that directory, then run
  `python scripts/refresh_hashes.py` to recompute every SHA-256 from real file
  bytes. Never hand-edit hashes without verifying them.
- **Compatibility rules.** Each entry declares `requires_app` (Plugin API v1
  supports `>=`, `<=`, `==`, `~=`) and `plugin_api: 1`. The application only
  offers versions whose range admits the running release; when no version is
  requested explicitly, the highest compatible version wins regardless of
  listing order.
- **Updates and rollback.** Installing a newer version activates it after full
  verification; the previous version directory stays on disk so users can roll
  back from the Installed tab. Reinstalling an identical verified version is
  idempotent — conflicting or corrupt same-version content is reported as an
  integrity error instead of being overwritten.

## Registry entry metadata

The legacy single `type` field remains for display compatibility. For plugins
that combine several capabilities (for example lint rules plus a job
template), the `capabilities` array is authoritative and must exactly match
the capabilities declared in the plugin manifest; CI rejects mismatches for
id, version, name, publisher, `requires_app`, plugin API version,
capabilities, and all manifest paths and hashes.

## Integrity hashes vs. publisher signatures

Every payload carries a SHA-256 chain (`registry.json → manifest.json →
files`). This verifies **integrity relative to this repository**: it detects
corruption or tampering in transit and pins exactly what was reviewed. It is
**not** a cryptographic publisher signature and does not protect against
compromise of the official repository itself. Signed registries using an
embedded public key are planned as future hardening beyond Plugin API v1.

## Citation/source expectations

Cluster command templates and application lint rules must cite their source:
TRUBA-specific commands reference the official TRUBA documentation (see each
plugin's `docs/sources.md`), and application rules cite vendor documentation
or observed behavior. Do not ship unverifiable commands "on style" — change
working commands only when tests or authoritative documentation justify it.

## Security notice

Cluster-profile plugins can define remote scheduler/status command templates
that are eventually executed over SSH by the main application after an
explicit user action. Review plugin content before installing it. See
[SECURITY.md](SECURITY.md) and [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and
[docs/CONTRIBUTOR_GUIDE.md](docs/CONTRIBUTOR_GUIDE.md).
Validation runs on every push and pull request via GitHub Actions.
