# TRUBA

TRUBA is available in the HPC Client GUI plugin registry as a declarative
Slurm cluster profile.

## Versions

- **1.0.0** — legacy profile fields and Slurm command templates; compatible
  with HPC Client GUI `>=1.4.0`.
- **1.1.0** — cluster-profile schema v2 with structured Home and Scratch
  metadata; requires HPC Client GUI `>=1.5.5` (schema v2 first shipped in
  1.5.5; 1.5.4 accepted schema 1 only).
- **1.2.0** — conservative structured storage and disabled quota metadata;
  requires HPC Client GUI `>=1.5.5`.
- **1.3.0** — refreshed ARF references and full storage template;
  requires HPC Client GUI `>=1.5.5`.
- **1.4.0** — cluster-profile schema v3 with declarative `job_outputs` and
  `file_filters`; requires HPC Client GUI `>=1.5.9` (the first release that
  validates schema 3). Published v1.5.8 supports schemas 1–2 only, so it is
  offered TRUBA 1.3.0 instead.
- **1.5.0** — cluster-profile schema v4 with declarative `job_details`,
  `accounting`, and `cluster_status` adapter/parser contracts; requires
  HPC Client GUI `>=1.5.9`.

## Storage

The profile describes `/arf/home/{user}` as Home and
`/arf/scratch/{user}` as Scratch. Scratch may be periodically cleaned, so
important data should be retained in an appropriate backed-up location.
The paths are informational defaults and can be edited in the connection
dialog.

## Quota monitoring

Quota metadata is present for future reviewed backend support, but monitoring
is disabled in the published profile. No quota command, filesystem probe, or
fallback usage query is run by installing or selecting the plugin.

## Security and scope

The plugin contains no credentials, accounts, hostnames, binaries, Python
modules, or remote installation hooks. Authentication and connection details
remain local to HPC Client GUI. This is **not** an official TÜBİTAK
ULAKBİM/TRUBA client.

## Sources

See the direct [ARF storage documentation](https://docs.truba.gov.tr/1-kaynaklar/arf/arf_depolama_kaynaklari.html),
[ARF connection documentation](https://docs.truba.gov.tr/1-kaynaklar/arf/arf_baglanti.html),
and [SSH documentation](https://docs.truba.gov.tr/2-temel_bilgiler/ssh_baglanti/index.html).
Verify current site policies, partitions, module availability, retention, and
access permissions with the cluster administrators before submitting jobs.
