# Consumer contract (application ↔ registry)

The registry and application validate each other against immutable release
refs. The registry-side `consumer-contract` job checks this checkout with the
application's real plugin contract suite.

## Current pin and capability generations

The current coordinated candidate pin is immutable application commit
`05e92dc558259bf307b6cbee13a07bd70c65079e`, which prepares v1.5.5. That
generation predates cluster-profile schemas 3–4 and asserts that *every*
published entry is installable by v1.5.5. Newer TRUBA releases (1.4.0 and
1.5.0) honestly require the first schema-3/4 capable application release
(v1.5.9), so the stale assertion cannot pass while the pin remains on the
v1.5.5 candidate. The job is therefore informational until the pin advances.

The blocking capability gate is the `validate` job: `scripts/validate_registry.py`
now fails closed when a cluster-profile payload's schema version predates its
declared `requires_app` floor, and `tests/test_compatibility.py` asserts the
latest-compatible fallback per supported application line.

## Advancing `APPLICATION_REF`

1. When a new application release becomes the oldest supported consumer
   (for example after v1.5.9 is published with schema-3/4 support), open a
   dedicated PR that updates:
    - `APPLICATION_REF` / `ref:` in the `consumer-contract` job of
      `.github/workflows/validate.yml` (required: v1.5.9 or newer);
    - `CURRENT_APP_VERSION` in `tests/test_compatibility.py`;
    - restore blocking behavior by removing `continue-on-error` from the
      `consumer-contract` job.
2. Both values must reference immutable tags, versions, or commits, never branches.
3. Confirm the job is green before merge.

The plugin registry is consumed by the HPC Client GUI application in two
directions, and both are guarded in CI:

## 1. Application side (pinned release contract)

The application's `contract` CI job checks out this registry at an explicit
immutable tag (`ref: v1.0.0` today) and runs its real
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

The `consumer-contract` job remains the mirror of the application's own
contract suite; it is informational until its pin advances to the first
schema-3/4 capable release.
