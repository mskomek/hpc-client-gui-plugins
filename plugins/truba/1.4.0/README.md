# TRUBA cluster profile plugin 1.4.0

This declarative Plugin API 1 profile provides conservative TRUBA/ARF
defaults for HPC Client GUI. It does not imply MareNostrum 5 behavior and is
not an official TÜBİTAK ULAKBİM/TRUBA client.

The profile keeps the validated `/arf/home/{user}` and `/arf/scratch/{user}`
paths from 1.3.0 and declares the two semantic Slurm output streams. Runtime
Slurm metadata resolves their actual paths; this package does not hardcode an
output filename.

Quota monitoring remains disabled. This package contains no credentials,
hosts, accounts, or live observations.

Sources are listed in `sources.md`.
