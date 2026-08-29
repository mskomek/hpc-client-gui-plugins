# Consumer contract (application ↔ registry)

The registry and application validate each other against immutable release
refs. The registry-side `consumer-contract` job checks this checkout with the
application's real plugin contract suite.

The current v2 consumer pin is application commit
`0c4e225b98245a8935a4090d50aa69827d157096` (the v1.5.4 contract update). Plugin API v2 engines are
hash-verified and loaded only after explicit user action; registry validation
never imports or executes them.

When advancing the pin, update `APPLICATION_REF` and the v2 compatibility
floor together, then require a green consumer-contract job before merging.
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
