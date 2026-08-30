# Consumer contract (application ↔ registry)

The registry and application validate each other against immutable release
refs. The registry-side `consumer-contract` job checks this checkout with the
application's real plugin contract suite.

The current coordinated candidate pin is immutable application commit
`05e92dc558259bf307b6cbee13a07bd70c65079e`, which prepares v1.5.5. After the
application PR is merged and v1.5.5 is published, replace it with that release
tag. The published v1.5.4 contract predates structured provider support and
cannot validate the newer registry entries. The current contract permits only
declarative Plugin API v1 packages and never imports plugin payloads.

When advancing the pin, update `APPLICATION_REF`, then require a green
consumer-contract job before merging.
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

## 2. Registry side (blocking consumer-contract job)

The `consumer-contract` job in this repository's `validate.yml` is the mirror
image and is **required/blocking** for every pull request:

- It tests **this checkout** (the proposed registry revision), never plugin
  `main` again.
- It checks out the latest supported application release at an explicit,
  immutable commit (`APPLICATION_REF`) and runs that
  application's real plugin contract, loader, and validator logic against the
  proposed revision.
- Payloads stay declarative-only: no executable plugin code and no
  installation hooks are introduced by or for this job.

## Advancing `APPLICATION_REF`

1. When a new application release becomes the oldest supported consumer
   (for example after v1.5.x is broadly deployed), open a dedicated PR that
   updates:
    - `APPLICATION_REF` / `ref:` in the `consumer-contract` job of
     `.github/workflows/validate.yml`;
   - `CURRENT_APP_VERSION` in `tests/test_compatibility.py`.
2. Both values must reference immutable tags, versions, or commits, never branches.
3. Confirm the job is green before merge; it blocks otherwise.
