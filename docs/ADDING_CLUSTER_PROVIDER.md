# Adding a cluster provider

Generate a package with the repository scaffolder:

```bash
python scripts/scaffold_cluster_profile.py --plugin-id org.hpcclient.example --profile-id example --name "Example HPC" --version 0.1.0 --requires-app ">=1.5.5" --template minimal --output-dir staging/example/0.1.0
```

1. Generate or copy the minimal template.
2. Fill identity and profile fields.
3. Add only verified paths and public help; leave quota and unknown fields blank/off.
4. Validate the package, then add its registry entry explicitly.
5. Run `python scripts/validate_registry.py`, `python -m pytest`, and `ruff check .`.
6. Open a pull request.

Use `templates/cluster-profile/full-profile.json` when every optional section
needs to be documented. Blank/null optional values are authoring data and do
not create actionable storage cards. Supported command placeholders are
`user`, `job_id`, `job_id_q`, `script_dir`, `script_dir_q`, `script_name`, and
`script_name_q`; unknown placeholders and multiline commands are rejected.

Published version directories are immutable. Manifests enumerate every file
with its actual byte size and SHA-256. Provider profiles and quota backends
are separate concerns: a provider may define storage without quota. Local
connection overrides are persisted by the application and never edit plugin
files. Quota is optional; a blank or disabled command causes no query.

TRUBA is an example only. Its published profile keeps quota disabled because
no automated command was verified for that release; `lssrv` is status output,
not quota. Do not copy credentials, hosts, accounts, or numeric limits.
