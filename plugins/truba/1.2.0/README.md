# TRUBA cluster profile plugin 1.2.0

This declarative profile provides conservative TRUBA/ARF defaults for HPC
Client GUI. It does not imply MareNostrum 5 behavior and is not an official
TÜBİTAK ULAKBİM/TRUBA client.

Home and Scratch use the documented `/arf/home/{user}` and
`/arf/scratch/{user}` paths. Backup and cleanup notes are informational only;
numeric limits and retention are intentionally absent. Public access/VPN help
is informational and must be checked against current official documentation.

Quota monitoring is disabled. No automated quota command was verified for
this release; `lssrv` remains the existing scheduler/status command and is not
a quota implementation. This package contains no credentials, hosts, accounts,
or live observations.

Sources: <https://www.truba.gov.tr/>.
