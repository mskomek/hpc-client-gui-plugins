# NCSA Delta sources

## Access
- https://docs.ncsa.illinois.edu/systems/delta/en/latest/user_guide/login.html — active Delta allocation, NCSA username, preferred login hostname, password, and Duo MFA.
- https://docs.ncsa.illinois.edu/systems/delta/en/latest/user_guide/accounts.html — allocation and account lifecycle guidance.

## Scheduler
- https://docs.ncsa.illinois.edu/systems/delta/en/latest/user_guide/running_jobs.html — Slurm use, current CPU/GPU partition names, job examples, and interactive/preemptible queue guidance.

## Storage
- https://docs.ncsa.illinois.edu/systems/delta/en/latest/index.html — Delta overview of node-local SSD scratch and parallel filesystems.
- https://docs.ncsa.illinois.edu/systems/delta/en/latest/user_guide/running_jobs.html — current filesystem dependencies and the HOME `/u` label.
- https://docs.ncsa.illinois.edu/systems/delta/en/latest/user_guide/software.html — current job examples; `module reset` populates WORK and SCRATCH.
- Exact account-specific paths are not hard-coded because NCSA's detailed data-management documentation is transitioning with the operating-system update.

## Quota
- No automatic quota query or site-specific quota value is included. Verify the user's limits with current NCSA guidance and the active allocation.

## Last verified
- 2026-10-14 against the official NCSA Delta documentation above.

## Known limitations
- This is the NCSA Delta profile, not DeltaAI.
- WORK and SCRATCH are documented in job-script context; verify their values in the active Delta environment before use.
- Allocation-specific project paths and quota values are intentionally not guessed.
- Partition names and limits may change; consult the current NCSA guide.
- This package is declarative community data, not an official NCSA or ACCESS product.