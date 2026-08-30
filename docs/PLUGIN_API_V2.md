# Plugin API v2 (linter tools)

Plugin API v2 is a **strictly additive** evolution of
[Plugin API v1](PLUGIN_API_V1.md). Everything documented for v1 remains
true: declarative data payloads, exact-file downloads, per-file SHA-256
verification, immutable version directories, official-registry-only
distribution.

## What v2 adds

Exactly one new capability, `linter-tool`, which allows a plugin to ship a
hash-verified **pure-Python linter engine** inside its payload:

```json
{
  "plugin_api": 2,
  "capabilities": ["linter-tool"],
  "entrypoints": {
    "linter_engine": "engine/ansys_lint/__init__.py"
  }
}
```

Rules enforced by the registry validator and the application:

- every `.py` payload file must carry the role `linter-engine`;
- the `linter-engine` role is only valid under `plugin_api: 2`;
- data files keep using `.json` (new role `linter-data`);
- the entrypoint path must point at a declared `linter-engine` file;
- all existing size/count/hash limits apply unchanged;
- nothing executes at install time. The engine module loads lazily and
  defensively when the user opens the tool; any failure is contained and
  reported without affecting other plugins or application startup.

## What v2 does NOT change

- v1 manifests remain exactly as before (`plugin_api: 1`).
- No third-party registries, no auto-updates, no install-time execution.
- Cluster profiles, lint rule packs and job templates behave identically.

## Compatibility contract

v2 plugins must declare `requires_app` ranges that exclude releases older
than the first application version implementing v2 (>= 1.5.0), so old
clients can never select a package they cannot load.
`tests/test_compatibility.py` enforces this on the registry side.

Because `raw.githubusercontent.com` cannot serve different content per
client version, adding the first v2 entry to `registry.json` means clients
older than 1.5.0 report the whole registry as unavailable until they are
upgraded - announced in the application release notes. From 1.5.0 onward,
the application's registry client tolerates entries with unsupported
`plugin_api` values by skipping them, so future additive generations do not
break Discover again.

## Engine entry-point contract

The file referenced by `entrypoints.linter_engine` must be an importable
package `__init__` exposing:

```python
def create_plugin() -> dict:
    return {
        "id": "...",
        "title": "...",
        "description": "...",
        "page_factory": callable,   # parent -> QWidget (PySide6, lazy import)
        "cli": "module.path",       # optional CLI module name
    }
```

The host wraps the dynamic import in defensive error handling and never
lets engine failures propagate into application state.

## Reference implementation

`plugins/ansys-lint/<version>/` ships the ANSYS Script & Journal Linter;
see [ANSYS_LINTER.md](ANSYS_LINTER.md).
