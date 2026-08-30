# hpc-client-gui-plugins

> Official declarative plugin registry for HPC Client GUI, including TRUBA and ANSYS Fluent integrations.

This repository is the **official declarative plugin registry** for
[HPC Client GUI](https://github.com/mskomek/hpc-client-gui).

Project links: [Wiki](https://github.com/mskomek/hpc-client-gui-plugins/wiki) ·
[Roadmap](ROADMAP.md) · [Citation](CITATION.cff)

![HPC Client GUI Plugin Manager showing the TRUBA and ANSYS Fluent plugins](https://raw.githubusercontent.com/mskomek/hpc-client-gui/main/docs/assets/plugin-manager.png)

## What lives here

- `registry.json` — the machine-readable index of published plugins.
- `schema/` — JSON Schemas for every plugin payload type (cluster profiles support v1/v2).
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
| TRUBA              | Cluster profile                   | 1.1.0          |
| ANSYS Fluent Tools | Journal lint + Slurm job template | 0.2.0          |

HPC Client GUI is an independent community project. It is **not** an official
TÜBİTAK ULAKBİM/TRUBA or ANSYS, Inc. product, and these plugins are not
provided by those organizations.

## Request a plugin

**You do not need to write any code to request a plugin.** Open a request
through the dedicated issue form:

**[→ Request a plugin](https://github.com/mskomek/hpc-client-gui-plugins/issues/new?template=plugin-request.yml)**

### Add a new HPC provider

Start with the [cluster provider tutorial](docs/ADDING_CLUSTER_PROVIDER.md).
If you only want to request support and do not want to write the profile,
use the [plugin request form](https://github.com/mskomek/hpc-client-gui-plugins/issues/new?template=plugin-request.yml).

Good requests include: support for another HPC center, a new Slurm cluster
profile, PBS/other scheduler profiles for future consideration, ANSYS Fluent
or OpenFOAM job templates, journal/job-script lint rules, and
institution-specific paths or queues.

Found an error in existing plugin content? Use the
[plugin content bug report](https://github.com/mskomek/hpc-client-gui-plugins/issues/new?template=plugin-content-bug.yml)
form. Application bugs (SSH/SFTP/FTP, UI, crashes) belong in
[HPC Client GUI issues](https://github.com/mskomek/hpc-client-gui/issues/new/choose).

Users install plugins from inside the application:
**HPC Client GUI → Plugins → Discover → Install** — no server-side setup on
the cluster is needed.

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
- **Cluster profile v2.** Structured `storage` and `quota_sources` sections
  use `schema_version: 2`; quota sources remain disabled unless the app has a
  reviewed backend, user consent, and an active connection.
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

## Links

- **Main application:** [mskomek/hpc-client-gui](https://github.com/mskomek/hpc-client-gui)
  — downloads, CLI guide, and full documentation.
- **Plugin Manager user guide:** [PLUGINS_en.md](https://github.com/mskomek/hpc-client-gui/blob/main/src/hpc_gui/docs/PLUGINS_en.md)
  ([Türkçe](https://github.com/mskomek/hpc-client-gui/blob/main/src/hpc_gui/docs/PLUGINS_tr.md)) —
  installing, activating, rolling back, and removing plugins.
- **Plugin development:** [cluster provider tutorial](docs/ADDING_CLUSTER_PROVIDER.md),
  [docs/CONTRIBUTOR_GUIDE.md](docs/CONTRIBUTOR_GUIDE.md),
  [docs/PLUGIN_API_V1.md](docs/PLUGIN_API_V1.md), and
  [docs/REGISTRY_PROTOCOL.md](docs/REGISTRY_PROTOCOL.md).
- **Release notes:** [docs/RELEASE_NOTES.md](docs/RELEASE_NOTES.md).
- **TRUBA Wiki draft:** [docs/WIKI_TRUBA.md](docs/WIKI_TRUBA.md).
- **Questions and discussion:** use
  [GitHub Discussions](https://github.com/mskomek/hpc-client-gui-plugins/discussions).
- **Bug reports:** plugin content problems go through the
  [plugin content bug form](https://github.com/mskomek/hpc-client-gui-plugins/issues/new?template=plugin-content-bug.yml);
  security issues follow [SECURITY.md](SECURITY.md) (private security advisory)
  and must never be opened as public issues.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and
[docs/CONTRIBUTOR_GUIDE.md](docs/CONTRIBUTOR_GUIDE.md).
Validation runs on every push and pull request via GitHub Actions.
