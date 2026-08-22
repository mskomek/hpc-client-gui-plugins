# Registry Protocol (exact-file distribution)

HPC Client GUI never downloads the whole repository. Installation uses an
**exact-file download protocol** against GitHub raw content.

## Base URLs

```text
Registry:  https://raw.githubusercontent.com/mskomek/hpc-client-gui-plugins/main/registry.json
Raw base:  https://raw.githubusercontent.com/mskomek/hpc-client-gui-plugins/main/
```

No GitHub API token, no release asset, and no repository ZIP is required.

## Discovery

1. The app downloads `registry.json` from the official raw URL.
2. It validates the registry schema (`schema/registry.schema.json`) and
   compatibility fields (`plugin_api`, `requires_app`).

## Install

For a registry entry such as:

```text
manifest_path    = plugins/truba/1.0.0/manifest.json
manifest_sha256  = <64 hex chars>
```

3. The app downloads exactly that manifest file.
4. It verifies the manifest SHA-256 against the registry entry.
5. It validates the manifest against `schema/manifest.schema.json`
   (paths, hashes, sizes, capabilities, compatibility).
6. For each entry in `manifest.files`, it downloads exactly
   `<manifest directory>/<file.path>` — nothing else.
7. Every downloaded file is SHA-256-verified before activation.
8. Files are installed into a staging directory.
9. Manifest/schema/compatibility checks run again on staged content.
10. Staging becomes the active version atomically; previous versions stay
    side-by-side for rollback.

## Integrity chain

```text
registry -> manifest SHA-256 -> payload file SHA-256s
```

This verifies integrity **against the registry**, not publisher identity: a
compromised official repository could change both the registry and the
hashes together. A signed registry using an application-embedded public key
is documented as a future hardening option — do not describe v1 as
publisher-signature security.
