# TRUBA cluster profile plugin

Official registry entry for HPC Client GUI: cluster profile.

## What it configures

This declarative plugin provides the TRUBA system template used by
[HPC Client GUI](https://github.com/mskomek/hpc-client-gui):

- Remote paths:
  - `home_dir`: `/arf/home/{user}`
  - `scratch_dir`: `/arf/scratch/{user}`
- Scheduler commands (Slurm):
  - `squeue_command`: `squeue -h -u {user} -o "%i|%P|%j|%u|%T|%M|%D|%C|%R"`
  - `sbatch_command`: `cd -- {script_dir_q} && sbatch -- {script_name_q}`
  - `scancel_command`: `scancel {job_id_q}`
  - `sacct_command`: `sacct -u {user} --format=JobID,JobName,State,Elapsed,MaxRSS,AllocTRES`
  - `scontrol_command`: `scontrol show job {job_id_q}`
  - `status_command`: `lssrv`
  - `active_job_ids_command`: `squeue -h -u {user} -o "%A"`
  - `job_state_command`: `sacct -n -X -j {job_id_q} -o State -P`

## Important notes

- This is **not** an official TÜBİTAK ULAKBİM/TRUBA client. It is a community
  cluster-profile definition for HPC Client GUI.
- The plugin contains **no credentials of any kind**: no username, password,
  key, token, or account name. Authentication stays entirely in your local,
  encrypted application settings.
- After applying the template, you may override any system field in the
  connection dialog; the template only pre-fills defaults.

## Installation

Install from inside HPC Client GUI via the Plugin Manager. No server-side
installation on the cluster is needed.

## Sources

Command templates follow standard Slurm usage; lssrv and the /arf paths
follow official TRUBA documentation: <https://www.truba.gov.tr/>. Verify
partition names and module availability for your account before submitting
jobs.
