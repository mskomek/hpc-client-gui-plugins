# Contributing

Thanks for considering a contribution to the official HPC Client GUI plugin
registry.

## Request a plugin

**You do not need to write any code to request a plugin.**

- Open your request through the dedicated issue form:
  [Plugin request](https://github.com/mskomek/hpc-client-gui-plugins/issues/new?template=plugin-request.yml)
- Provide official, public documentation for the cluster or application
  whenever possible — that is what maintainers validate content against.
- Requests for new cluster profiles, Slurm/solver job templates (for example
  ANSYS Fluent or OpenFOAM), and journal/job-script lint rules are all welcome.
- A request does not guarantee inclusion; maintainers may split a broad request
  into separate cluster-profile, job-template, and lint-rule work.
- All contributed plugin content must remain **declarative**: no executable
  code, no scripts intended for automatic execution, no binary payloads, no
  credentials, and no licensed/proprietary files.
- Cluster-specific data in examples must be sanitized.
- Found an error in existing plugin content? Use the
  [plugin content bug report](https://github.com/mskomek/hpc-client-gui-plugins/issues/new?template=plugin-content-bug.yml)
  form instead. Application runtime bugs go to
  [HPC Client GUI issues](https://github.com/mskomek/hpc-client-gui/issues/new/choose).

Users install plugins from inside the application:
**HPC Client GUI → Plugins → Discover → Install**.

## Ground rules

1. Plugins are **declarative data only**. Never add Python modules, DLLs,
   executables, shell/PowerShell hooks, or dynamically loaded content under
   `plugins/`. Repository maintenance scripts under `scripts/` are the only
   Python allowed here and are never distributed as plugin payloads.
2. Once a plugin version directory has been merged to `main`, treat it as
   immutable. Fix problems by publishing a **new version directory** and a new
   registry entry; never mutate published hashes in place.
3. Plugin IDs are stable reverse-domain-like identifiers
   (for example `org.hpcclient.truba`). Never derive identity from the display
   name.
4. Every change must pass local validation before you open a PR:
   `python scripts/validate_registry.py` and `python -m pytest`.
5. Do not invent site-specific facts (hostnames, partitions, scheduler
   commands) that you cannot verify from an authoritative source.

## Workflow

```text
fork / branch  ->  edit schemas, plugins, or docs
               ->  python scripts/refresh_hashes.py   # if payload files changed
               ->  python scripts/validate_registry.py
               ->  python -m pytest
               ->  open pull request
```

CI runs the same validation on every push and pull request.

## Review focus for cluster profiles

Because cluster profiles contain remote command templates that the desktop
app eventually runs over SSH after explicit user action, reviewers pay
special attention to:

- quoted argument handling (`-- {var_q}` style placeholders);
- no destructive commands (`rm`, `chmod`, credential access) hidden in
  command fields;
- paths matching the documented cluster layout.
