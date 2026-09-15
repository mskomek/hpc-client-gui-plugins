# Published plugin immutability

## The rule

Once a plugin version is published into `registry.json`, its
`plugins/<plugin>/<version>/manifest.json` and every file that manifest
declares are **immutable**. They may never change again, for any reason.

A published package is something users have already downloaded and
hash-verified. Rewriting its bytes silently changes what an installed client
believed it had, and makes the registry's own integrity hashes meaningless as
a historical record.

Consequences:

- Any content change requires a **new plugin version**. Never edit a
  historical version directory for a cluster-profile change, a payload
  documentation fix, a manifest update, a declared README/source change, or a
  feature change.
- A compatibility mistake discovered after publication is corrected at the
  **registry level**, not in the package (see below).

## What enforces it

`published-plugin-lock.json` is the ledger. It records, per published
`<plugin-id>@<version>`, the manifest SHA-256 and the SHA-256 of every
declared payload file.

`scripts/validate_registry.py` fails closed when a package in the ledger no
longer matches it, with:

```
Published plugin org.hpcclient.truba@1.4.0 is immutable.
Create a new plugin version instead of modifying its payload.
```

The ledger is a **separate source of truth**. It is deliberately not written
by `scripts/refresh_hashes.py` and not regenerated during validation, so the
otherwise plausible sequence

1. edit a published payload,
2. regenerate the manifest file hashes,
3. regenerate the registry `manifest_sha256`,

does **not** produce a green validation. The integrity hashes agree with each
other afterwards; the ledger does not, and the ledger wins. Hash integrity and
published immutability are separate properties: a correctly regenerated hash
never legalises a historical mutation.

Freezing a genuinely new publication is an explicit, additive action:

```bash
python scripts/published_lock.py --record org.hpcclient.truba@1.6.0
```

It refuses to overwrite a version that is already frozen.

`tests/test_published_immutability.py` runs the real validator against a
throwaway repository copy for the full matrix: unchanged package passes;
manifest, payload, and declared-documentation changes fail; a new version
passes; a registry-only compatibility override passes; and a mutation with
regenerated hashes still fails.

## Registry-level compatibility override

Package bytes are immutable; a compatibility *decision* is correctable. A
registry entry may carry:

```json
"compatibility_override": {
  "requires_app": ">=1.5.9",
  "reason": "why the published floor was wrong",
  "recorded": "2026-09-15"
}
```

Precedence:

```
effective_requires_app = compatibility_override.requires_app  (if present)
                         else the immutable manifest requires_app
```

Rules:

- An override may only **narrow** compatibility (raise the floor). Widening is
  rejected by `scripts/schema_compatibility.py`, because it would let the
  registry advertise an install the application must refuse.
- An override affects **discovery, offerability, and resolution only**.
- It can never override unsupported-schema rejection, payload validation,
  manifest hash integrity, or declared payload integrity. **The installer
  validation in the application is the final authority**; a registry claim of
  "compatible" does not make an unsupported cluster-profile schema
  installable, and the application rejects it fail-closed.

An override is only useful to clients new enough to read it. A release that
predates the field reads `requires_app` directly, which is why the historical
corrections below were frozen in place rather than reverted.

## Recorded one-time exceptions

The ledger's `frozen_reason` field documents every package whose published
bytes were altered before this policy was machine-enforced. These are
historical violations, deliberately made visible rather than erased:

| Package | Violation |
| --- | --- |
| `org.hpcclient.truba@1.1.0` | `requires_app` corrected in place `>=1.5.4` → `>=1.5.5` (commit `602e904`, 2026-09-14). |
| `org.hpcclient.truba@1.2.0` | `requires_app` corrected in place `>=1.5.4` → `>=1.5.5` (commit `602e904`). |
| `org.hpcclient.truba@1.4.0` | `requires_app` corrected in place `>=1.5.8` → `>=1.5.9` (commit `602e904`), because released 1.5.8 validates cluster-profile schemas 1-2 only. |
| `org.hpcclient.truba@1.5.0` | `README.md` and `sources.md` added and declared during the 2026-09-15 reconciliation. The version requires app `>=1.5.9`, which has never been released, so no client can have installed the earlier bytes. |

The original bytes remain recoverable from git history. They were **not**
restored: the correction protects already-released clients that read
`requires_app` directly and have no knowledge of `compatibility_override`.
Restoring the original floors would re-advertise those packages to releases
that cannot validate their payload schema.

From the ledger baseline (2026-09-15) onward there are no further exceptions.
Every future compatibility correction goes through `compatibility_override`,
and every content change goes through a new plugin version.
