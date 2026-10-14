# JSC JUWELS cluster profile

Independent community data package; not endorsed by Forschungszentrum Jülich or JSC. It stores no usernames, credentials, project IDs, or budget values.

JUWELS has distinct Cluster and Booster login endpoints. Use the endpoint that matches the target partition. JSC access requires an assigned resource project and public-key setup through JuDoor; if TOTP MFA is enabled, SSH requests a one-time code after key verification. Always verify the presented host fingerprint against JuDoor.

The profile lists the current documented Slurm partitions: `batch`, `mem192`, `devel`, `gpus`, `booster`, `develbooster`, `large`, and `largebooster`. The large partitions require coordination with JSC support. Partition availability, limits, and project eligibility can change; check the live guide before submitting work.

Storage resolves `$HOME`, `$PROJECT`, and `$SCRATCH` from the remote environment. Activate the intended project with `jutil env activate` before relying on `$PROJECT`. JSC describes scratch as temporary, unbacked storage with automatic cleanup; do not treat it as an archive. No project quota, username, host fingerprint, or allocation-specific path is guessed.

Last verified: 2026-10-14 against the official sources listed in `sources.md`.
