# Contributing

Thanks for considering a contribution to the official HPC Client GUI plugin
registry.

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
