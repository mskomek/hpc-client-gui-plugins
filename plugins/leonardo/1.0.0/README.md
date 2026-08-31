# CINECA Leonardo cluster profile

Independent community profile; not endorsed by CINECA. Leonardo access
requires the external Smallstep/2FA certificate flow. Complete that flow
outside HPC Client GUI; the plugin does not run `step ssh login`.

Storage paths are resolved from the remote `$HOME`, `$WORK`, `$FAST`,
`$SCRATCH`, `$PUBLIC`, and `$DRES` variables. Quota uses the reviewed
application-owned `cinQuota` parser.

Last verified: 2026-08-31. Certificate validity and scheduler policies can
change; consult the linked official CINECA documentation.
