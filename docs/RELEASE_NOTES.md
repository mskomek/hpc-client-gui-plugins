# Release notes

## TRUBA 1.1.0

- Requires HPC Client GUI `>=1.5.0`.
- Moves the cluster profile to payload schema v2.
- Adds structured Home and Scratch storage metadata.
- Declares quota metadata but keeps monitoring disabled because no verified
  automated TRUBA quota command is published.
- Preserves the existing Slurm commands and `/arf` path templates.

This release contains declarative data only and no credentials, executable
hooks, or server-side installation steps.
