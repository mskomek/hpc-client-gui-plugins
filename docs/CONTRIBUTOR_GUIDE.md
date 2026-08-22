# Contributor Guide

This guide explains how to add or update a plugin in the official registry.

## 1. Choose identity

- Pick a stable reverse-domain-like ID (`org.hpcclient.<name>`).
- Use semantic versioning. Start new plugins at `0.1.0` unless the plugin is
  considered production-ready from day one.
- Declare only capabilities from the v1 vocabulary:
  `cluster-profile`, `lint-rules`, `job-template`, `application-tools`.

## 2. Create the version directory

```text
plugins/<short-name>/<version>/
├── manifest.json
└── <payload files declared in manifest.files>
```

Manifest file paths are relative to this directory. Allowed extensions are
`.json`, `.md`, and `.txt`.

## 3. Write the payload

- Cluster profiles: follow `schema/cluster-profile.schema.json`. Quote
  interpolated values with the `{var_q}` placeholder style. Never include
  destructive commands. Never invent site facts you cannot verify.
- Lint rules: follow `schema/lint-index.schema.json` +
  `schema/lint-rule.schema.json`. Rules are declarative match kinds handled
  by the application's lint engine.
- Templates: follow `schema/template-index.schema.json` +
  `schema/template.schema.json`.

## 4. Register the plugin

Add an entry to `registry.json` with the correct `manifest_path` and
`manifest_sha256`. Then run:

```bash
python scripts/refresh_hashes.py     # optional: recompute hashes for you
python scripts/validate_registry.py # must print OK
python -m pytest                    # must pass
```

## 5. Open a pull request

CI validates every push and PR. Reviewers check schema conformance, hash
consistency, path safety, and — for cluster profiles — the safety of command
templates.

## 6. After merge

Published versions are immutable. To change a plugin, create a new version
directory, add a new registry entry, and remove nothing.
