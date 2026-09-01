# TRUBA cluster profile plugin 1.1

This version uses cluster-profile schema v2. It adds structured Home and
Scratch metadata while preserving the existing Slurm commands and paths.

Quota monitoring is intentionally disabled: no verified automated TRUBA quota
command is included. The plugin contains no credentials or host-specific
connection settings; authentication remains local to HPC Client GUI.

This is **not** an official TÜBİTAK ULAKBİM/TRUBA client.
