# TACC Frontera sources

## Access
- https://docs.tacc.utexas.edu/hpc/frontera/ — Frontera allocation requirement, `frontera.tacc.utexas.edu`, SSH, and MFA requirement.
- https://docs.tacc.utexas.edu/basics/mfa/ — TACC password and second-factor login prompts.

## Scheduler
- https://docs.tacc.utexas.edu/hpc/frontera/ — Slurm queues and job-submission guidance. The guide warns that all Frontera queues close permanently on 2026-10-15; it says filesystems remain available for data transfer after closure. Queue names are intentionally omitted from this package.

## Storage
- https://docs.tacc.utexas.edu/hpc/frontera/ — `$HOME`, `$WORK`, `$SCRATCH`, backup/purge notes, quotas, and current scratch-system status. The profile resolves environment variables rather than guessing account-specific paths.

## Quota
- https://docs.tacc.utexas.edu/hpc/frontera/ — documents storage allowances. No automated quota command is enabled by this package.

## Last verified
- 2026-10-14 against the official TACC documentation above.

## Known limitations
- Frontera's compute queues are scheduled to close permanently on 2026-10-15. TACC says file transfer access will remain after queue closure.
- Queue availability and limits can change; check current TACC notices and live guidance.
- Allocation IDs and user paths are account-specific and are not included.
- This package is declarative community data, not an official TACC product.