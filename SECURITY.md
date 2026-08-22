# Security Policy

## Supported scope

This repository hosts **declarative plugin data** for HPC Client GUI
(Plugin API v1). It contains no runtime code that is executed on user machines
or HPC clusters; the Python files under `scripts/` are developer validation
tooling only.

## Reporting a vulnerability

Report suspected vulnerabilities in this registry or in the HPC Client GUI
plugin system via [GitHub Security Advisories](../../security/advisories/new)
on the affected repository, or open an issue only if the report contains no
sensitive detail. Please do not publish exploit details before a fix is
available.

Please include:

- the affected plugin ID and version directory;
- the schema or protocol step involved;
- a minimal reproduction (paths, hashes, JSON snippets).

## What we consider in scope

- path traversal or absolute-path injection in `manifest.files[].path`;
- SHA-256/size mismatch between registry, manifests, and payload files;
- executable or hook content smuggled into declarative payloads;
- command-template injection risks in `cluster-profile` plugins;
- registry metadata spoofing (IDs, versions, publisher fields).

## Security model

See [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) for what Plugin API v1
guarantees — and explicitly does **not** guarantee (integrity is verified
against this registry, but a compromised official repository could still
change both registry and hashes; a signed registry is a planned hardening
step).
