# TACC Frontera cluster profile

Independent community package; not endorsed by TACC. It contains declarative
connection and storage guidance only and stores no usernames, credentials, or
allocation values.

**Retirement notice:** TACC's current guide says the Frontera queues close
permanently on 2026-10-15. After closure, the filesystems remain accessible
for data transfer. This package deliberately supplies no fixed queue names or
job command templates. Check TACC's live guidance before any transfer or use.

The profile uses the documented `$HOME`, `$WORK`, and `$SCRATCH` environment
variables. TACC documents HOME as backed up and not purged, WORK as unbacked
and not purged, and SCRATCH as subject to purge after 10 days without access.

Last verified: 2026-10-14.