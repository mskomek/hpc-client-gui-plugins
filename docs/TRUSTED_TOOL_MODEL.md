# Trusted Tool Model

Cluster provider packages remain data-only. They contain profiles, templates,
metadata, and documentation; they do not execute Python, shell hooks, or
binaries.

ANSYS Script & Journal Linter is a separate Trusted Tool because its parser
engine is executable code. Only the application-owned allowlist can authorize
its exact ID, publisher, API, entrypoint, and verified package hashes. A
manifest declaring `linter-tool` does not grant execution permission.

Trusted tools are first-party or repository-reviewed components. This is not a
general third-party plugin execution API. Tools receive only selected input
and return lint results; they do not receive SSH credentials, keyring access,
provider-registry write access, updater keys, or automatic network/subprocess
capabilities.

The legacy `plugin_api: 2` field is retained only as a package compatibility
marker while the reviewed ANSYS package migrates to this model. It must never
be interpreted as generic permission to import downloaded Python.
