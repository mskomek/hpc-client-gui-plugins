# TRUBA cluster profile plugin 1.3.0

This declarative Plugin API 1 profile provides conservative TRUBA/ARF
defaults for HPC Client GUI. It does not imply MareNostrum 5 behavior and is
not an official TÜBİTAK ULAKBİM/TRUBA client.

Home and Scratch use the documented `/arf/home/{user}` and
`/arf/scratch/{user}` paths. Backup and cleanup notes are informational;
numeric limits, retention, quotas, and measured usage are intentionally absent.
Public access and VPN/SSH help are informational and must be checked against
the current official documentation.

Quota monitoring is disabled. No automated quota command was verified for
this release; `lssrv` remains the scheduler/status command and is not quota.
This package contains no credentials, hosts, accounts, or live observations.

Sources:

- <https://docs.truba.gov.tr/1-kaynaklar/arf/arf_depolama_kaynaklari.html>
- <https://docs.truba.gov.tr/1-kaynaklar/arf/arf_baglanti.html>
- <https://docs.truba.gov.tr/2-temel_bilgiler/ssh_baglanti/index.html>
