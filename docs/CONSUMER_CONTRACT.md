# Consumer contract (application ↔ registry)

The registry and application validate each other against immutable release
refs. The registry-side `consumer-contract` job checks this checkout with the
application's real plugin contract suite.

## Current pin and capability generations

The current coordinated pin is the immutable application commit
`55eb70920f5cac27722ce76a435f0a318716c5c2`. That commit validates
cluster-profile schemas 1-4 and carries the capability-aware contract suite,
so it can honestly evaluate every entry this registry publishes, including
TRUBA 1.4.0 and 1.5.0.

The published `v1.5.8` release (`063d83b523be377d4ef02dc8a61e2fdd15876ecc`)
supports cluster-profile schemas 1-2 only. Pinning the contract to that
release asserted that *every* published entry is installable by it, which is
false for schema-3/4 payloads; that stale assertion is why the job was
previously non-blocking. The pin is now capability-correct and the job is
**blocking** again.

The pin is an immutable commit SHA because no schema-3/4 capable application
release has been published yet. Policy: the pin is always an immutable tag or
an immutable commit SHA, never a mutable branch ref. Replace the SHA with the
corresponding immutable release tag when such a release is published. This
document does not claim that any such release exists today.

Plugin API v2 engines are hash-verified and loaded only after explicit user
action; registry validation never imports or executes them.

The second blocking capability gate is the `validate` job:
`scripts/validate_registry.py` fails closed when a cluster-profile payload's
schema version predates its declared `requires_app` floor, and
`tests/test_compatibility.py` asserts the latest-compatible fallback per
supported application line.

## Advancing `APPLICATION_REF`

1. When a new application release becomes the oldest supported consumer,
   open a dedicated PR that updates:
    - `APPLICATION_REF` / `ref:` in the `consumer-contract` job of
      `.github/workflows/validate.yml` (immutable tag or commit SHA);
    - `CURRENT_APP_VERSION` in `tests/test_compatibility.py`;
    - the v2 compatibility floor, when it moves with the pin.
2. Both values must reference immutable tags, versions, or commits, never
   branches.
3. Confirm the job is green before merge; it blocks otherwise.

The plugin registry is consumed by the HPC Client GUI application in two
directions, and both are guarded in CI:

## 1. Application side (pinned release contract)

The application's `contract` CI job checks out this registry at an explicit
immutable commit (`ref: a320cde6affe9072523a49352b2d688e050168b3` today) and runs its real
`tests/test_plugin_contract.py` suite against it. The pin exists so a release
is always built against exactly the registry contents it was tested with.

Advancing: bump the `ref:` in `.github/workflows/ci.yml` of the application
repository when a new registry tag has passed the consumer-contract job here,
and record it in the application release notes.

## 2. Registry side (blocking capability gate)

The `validate` job in this repository's `validate.yml` is **required/blocking**
for every pull request:

- It tests **this checkout** (the proposed registry revision), never plugin
  `main` again.
- It checks the payload schema floors against the application capability
  matrix in `scripts/schema_compatibility.py` and fails closed when a newer
  payload schema claims an application release that predates it.
- It runs `tests/test_compatibility.py`, which asserts the latest-compatible
  fallback for every supported application line.
- Payloads stay declarative-only: no executable plugin code and no
  installation hooks are introduced by or for this job.

The `consumer-contract` job is the mirror of the application's own contract
suite and is **blocking**: it runs the pinned application's real plugin
contract, loader, installer, and validator logic against this checkout.
