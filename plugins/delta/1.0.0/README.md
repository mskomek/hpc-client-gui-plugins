# NCSA Delta cluster profile

Independent community package; not endorsed by NCSA or ACCESS. It describes
NCSA Delta, not DeltaAI, and stores no usernames, credentials, or allocation
values.

The profile uses the NCSA login hostname and password-plus-Duo MFA described
in the Delta login guide. It lists the Slurm partitions in the current Delta
job guide. Confirm availability, allocation, and limits before submitting a
job.

NCSA's job examples say `module reset` populates `WORK` and `SCRATCH`. These
paths are allocation-dependent; verify them in the active Delta environment.
The Delta documentation is transitioning after its operating-system update,
so this package does not pin per-user quotas or project paths. Automatic quota
queries are disabled.

Last verified: 2026-10-14.