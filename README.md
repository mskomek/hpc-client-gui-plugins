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

## Security notice

Cluster-profile plugins can define remote scheduler/status command templates
that are eventually executed over SSH by the main application after an
explicit user action. Review plugin content before installing it. See
[SECURITY.md](SECURITY.md) and [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and
[docs/CONTRIBUTOR_GUIDE.md](docs/CONTRIBUTOR_GUIDE.md).
Validation runs on every push and pull request via GitHub Actions.
