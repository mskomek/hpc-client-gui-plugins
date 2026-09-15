# Release notes

## Registry policy (2026-09-15)

- Published plugin packages are now machine-enforced immutable. See
  [PUBLISHED_PLUGIN_IMMUTABILITY.md](PUBLISHED_PLUGIN_IMMUTABILITY.md) and
  `published-plugin-lock.json`.
- Registry entries may carry a `compatibility_override` that narrows (never
  widens) an already published `requires_app`. It affects discovery,
  offerability, and resolution only; the application installer's
  unsupported-schema rejection, payload validation, and hash integrity checks
  remain the final authority.
- The `consumer-contract` job is blocking again and is pinned to an immutable
  schema-3/4 capable application commit.
- TRUBA 1.5.0 gained the `README.md` and `sources.md` every other cluster
  profile package ships. That completion is recorded as a one-time frozen
  exception in the ledger: the version requires application `>=1.5.9`, which
  has never been released, so no consumer can have installed the earlier
  bytes.

## TRUBA 1.5.0

- Requires HPC Client GUI `>=1.5.9`.
- Moves the cluster profile to payload schema v4 with declarative
  `job_details`, `accounting`, and `cluster_status` adapter/parser contracts.
- Published application releases before 1.5.9 cannot validate schemas 3–4 and
  must not install this version.

## TRUBA 1.4.0

- Requires HPC Client GUI `>=1.5.9` (corrected from the originally published
  `>=1.5.8` claim, which predated schema-3 support).
- Moves the cluster profile to payload schema v3 with declarative
  `job_outputs` and `file_filters`.
- The v1.5.8 release supports cluster-profile schemas 1–2 only; users on
  v1.5.8 are offered TRUBA 1.3.0 as the newest compatible version.

## TRUBA 1.1.0

- Requires HPC Client GUI `>=1.5.5` (schema v2 first shipped in 1.5.5; the
  originally published `>=1.5.0` marker was inaccurate).
- Moves the cluster profile to payload schema v2.
- Adds structured Home and Scratch storage metadata.
- Declares quota metadata but keeps monitoring disabled because no verified
  automated TRUBA quota command is published.
- Preserves the existing Slurm commands and `/arf` path templates.

This release contains declarative data only and no credentials, executable
hooks, or server-side installation steps.
