# TRUBA cluster profile plugin 1.5.0

This declarative Plugin API 1 profile provides conservative TRUBA/ARF
defaults for HPC Client GUI. It does not imply MareNostrum 5 behavior and is
not an official TÜBİTAK ULAKBİM/TRUBA client.

The profile keeps the validated `/arf/home/{user}` and `/arf/scratch/{user}`
paths and the semantic Slurm output streams from 1.4.0, and moves the payload
to cluster-profile schema v4 by declaring the adapter/parser contracts the
application uses for job details, accounting, and cluster status. The
declarations name application-side adapters and parsers only; no command
output is interpreted inside this package.

Quota monitoring remains disabled. This package contains no credentials,
hosts, accounts, or live observations.

Schema v4 is validated by HPC Client GUI `>=1.5.9`. Earlier releases must use
TRUBA 1.3.0 (schemas 1-2).

Sources are listed in `sources.md`.
