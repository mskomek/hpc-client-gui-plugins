# Contributor Guide

This guide explains how to add or update a plugin in the official registry.

## 1. Choose identity

- Pick a stable reverse-domain-like ID (`org.hpcclient.<name>`).
- Use semantic versioning. Start new plugins at `0.1.0` unless the plugin is
  considered production-ready from day one.
- Declare only capabilities from the Plugin API vocabulary:
  `cluster-profile`, `lint-rules`, `job-template`, `application-tools`.

## 2. Create the version directory

```text
plugins/<short-name>/<version>/
├── manifest.json
└── <payload files declared in manifest.files>
```

Manifest file paths are relative to this directory. Allowed extensions are
`.json`, `.md`, `.txt`, and `.tpl`. Every file inside the version directory
must be declared in `manifest.files`; undeclared extra files are rejected.

## 3. Write the payload

- Cluster profiles: follow `schema/cluster-profile.schema.json`. Use
  `schema_version: 1` for legacy payloads or `schema_version: 2` for the
  structured `storage`/`quota_sources` model. Quote
  interpolated values with the `{var_q}` placeholder style. Never include
  destructive commands. Never invent site facts you cannot verify.
- Lint rules: follow `schema/lint-index.schema.json` +
  `schema/lint-rule.schema.json`. Rules are declarative match kinds handled
  by the application's lint engine. Vendor-specific rules (for example
  Fluent) must cite official documentation in `docs/sources.md`; never copy
  command manuals into the repository.
- Templates: follow `schema/template-index.schema.json` +
  `schema/template.schema.json`. Template content uses the limited
  `{{variable}}` placeholder syntax with typed variables
  (`string`, `integer`, `boolean`, `choice`, `path`). Do not hardcode
  unverified site-specific resource defaults; prefer required variables.
- `.tpl` template files: plain-text scheduler script skeletons (for example
  a Slurm submission script for ANSYS Fluent). A `.tpl` file is data, never
  executed at install time; the app only reads it as text and renders
  declared `{{variable}}` placeholders when the user explicitly creates a job
  from the template. Declare each `.tpl` in `manifest.files` with role
  `template-content`, list it in the template index entrypoint
  (`template_index`) via its `content_path` plus a matching `sha256`, and
  keep routing inside the index — the application never discovers `.tpl`
  files by scanning directories. See
  `plugins/fluent/0.2.0/templates/fluent_job.slurm.tpl` for a reference.

For a minimal profile, generate a starting payload with:

```bash
python scripts/scaffold_cluster_profile.py --profile-id my-site --name "My Site" --output cluster-profile.json
```

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
