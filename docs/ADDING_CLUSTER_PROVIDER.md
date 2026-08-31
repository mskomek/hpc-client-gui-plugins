# Adding a cluster provider

A cluster provider is a declarative plugin describing institution-specific
defaults: cluster identity, Slurm guidance, known storage locations, public
documentation, and optional quota integration. Provider plugins live in
[`hpc-client-gui-plugins`](https://github.com/mskomek/hpc-client-gui-plugins).
They install no software on the HPC cluster, contain no credentials, create no
user directories, and do not imply institutional endorsement.

## Before you start

Collect facts from public documentation or an HPC administrator. **Unknown is
better than guessed.** Do not invent quota values, partitions, paths, account
names, private hostnames, credentials, VPN configuration, or undocumented
commands.

| Information | Required? | Example |
| --- | --- | --- |
| Public provider name | Yes | Example University HPC |
| Scheduler | Yes | Slurm |
| Public documentation URL | Recommended | `https://hpc.example.edu/docs` |
| Home path | Optional | `/home/{user}` |
| Scratch path | Optional | `/scratch/{user}` |
| Project path | Optional | `/project/<group>` |
| Partition names | Optional | `cpu`, `gpu` |
| Account guidance | Optional | Use your project allocation |
| Software notes | Optional | Modules are available via Lmod |
| Quota command | Optional | Only if officially verified |

## Fork, clone, and branch

Fork the plugin repository on GitHub, then clone your fork:

```bash
git clone https://github.com/<your-user>/hpc-client-gui-plugins.git
cd hpc-client-gui-plugins
git checkout -b add-example-university-provider
```

The normal flow is fork, branch, provider changes, validation, commit, and a
pull request against `mskomek/hpc-client-gui-plugins`.

## Generate the package

Use the scaffolder. This complete example creates a package in staging:

```bash
python scripts/scaffold_cluster_profile.py \
  --plugin-id org.hpcclient.example \
  --profile-id example \
  --name "Example University HPC" \
  --version 0.1.0 \
  --requires-app ">=1.5.5" \
  --publisher "Example University HPC contributor" \
  --description "Cluster profile for Example University HPC." \
  --template minimal \
  --output-dir staging/example/0.1.0
```

`--plugin-id` is the stable reverse-domain-like registry ID. `--profile-id` is
the short stable ID used inside the profile. `--name` is the displayed name;
`--version 0.1.0` is a sensible first semantic version. `--requires-app` is
the minimum compatible GUI version. `--publisher` and `--description` are
public manifest metadata. `--template` is `minimal` or `full`, and
`--output-dir` is the package directory. Keep IDs stable after publishing.

The generated result is:

```text
staging/example/0.1.0/
├── manifest.json
├── cluster-profile.json
└── README.md
```

`manifest.json` declares identity, compatibility, capability, files, and
payload hashes. `cluster-profile.json` is the data consumed by HPC Client
GUI. `README.md` is the human-readable package description.

## Choose a template

`minimal` is recommended: it gives you identity, Slurm, empty storage, and
empty quota data. `full` includes the optional metadata, site,
scheduler-hints, and software sections so you can fill only the facts you can
verify. The source templates are
[`minimal-profile.json`](../templates/cluster-profile/minimal-profile.json),
[`full-profile.json`](../templates/cluster-profile/full-profile.json), and
[`FIELD_GUIDE.md`](../templates/cluster-profile/FIELD_GUIDE.md). Empty optional
fields are valid; do not fill fields merely because they exist.

## Edit `cluster-profile.json`

The fictional values below are a complete Example University HPC illustration,
not real site information:

```json
{
  "schema_version": 2,
  "profile_id": "example",
  "name": "Example University HPC",
  "scheduler": "slurm",
  "description": "Fictional public-style example provider.",
  "metadata": {
    "maintainer": "Example University HPC contributor",
    "documentation_url": "https://hpc.example.edu/docs",
    "support_url": "https://hpc.example.edu/support"
  },
  "site": {
    "public_name": "Example University HPC",
    "region": "Europe",
    "access_note": "Institutional HPC account required.",
    "documentation_url": "https://hpc.example.edu/docs"
  },
  "scheduler_hints": {
    "queue_notes": "CPU jobs normally use the cpu partition.",
    "account_notes": "Specify the allocation assigned by the institution.",
    "partitions": ["cpu", "gpu"]
  },
  "software": {
    "module_paths": [],
    "setup_notes": "Software is normally loaded using environment modules."
  },
  "storage": [
    {"id": "home", "label": "Home", "kind": "home", "enabled": true,
     "path_template": "/home/{user}", "access_context": "login-node",
     "policy": {"backup": null, "retention_days": null}},
    {"id": "scratch", "label": "Scratch", "kind": "scratch", "enabled": true,
     "path_template": "/scratch/{user}", "access_context": "login-node",
     "policy": {"backup": null, "retention_days": null}}
  ],
  "quota_sources": []
}
```

The required identity fields are `schema_version`, `profile_id`, `name`, and
`scheduler`. `metadata` and `site` contain public maintainer, support, region,
and documentation information. `scheduler_hints` is guidance, not a promise:
list partitions only when verified. `software` describes modules and setup in
plain language; it is not arbitrary shell initialization code.

If verified, add storage entries such as these. The policy values are examples
only and must not be copied without explicit institutional documentation:

```json
"storage": [
  {"id": "home", "label": "Home", "kind": "home", "enabled": true,
   "path_template": "/home/{user}", "access_context": "login-node",
   "policy": {"backup": true, "retention_days": null}},
  {"id": "scratch", "label": "Scratch", "kind": "scratch", "enabled": true,
   "path_template": "/scratch/{user}", "access_context": "login-node",
   "policy": {"backup": false, "retention_days": 30}}
]
```

Common kinds are `home`, `scratch`, `project`, `custom`, and `node-local`.
Storage metadata helps users recognize where they are browsing, understand
where output belongs, associate job working/output paths with an area, and
learn each area's purpose. `{user}`, `{user_first}`, `{project}`, and `{account}`
are application-owned placeholders. Missing project/account values are never
guessed. A resolver may use only a path template or the allow-listed remote
variables `HOME`, `SCRATCH`, `WORK`, and `PROJECT`; it cannot contain commands
or arbitrary environment names. `access.auth_methods` is descriptive and does
not grant automatic support. Optional `requirements.project` and
`requirements.account` describe values the user may need to provide.

## Quota monitoring is optional

A provider is useful without quota support. Storage descriptions and quota
queries are separate. You may describe Home, Scratch, and Project storage
without defining a quota command.

If no command is officially verified, omit `quota_sources` or use an explicitly
disabled record. Adding a `quota_sources` row does not implement quota support:
`backend_id` must name a reviewed backend already allow-listed by HPC Client
GUI. Provider plugins cannot ship executable quota parsers or arbitrary quota
code.

```json
"quota_sources": [{"id": "example-quota", "enabled": false,
  "backend_id": "", "command_template": "", "scope": "unknown"}]
```

Disabled or blank quota means: no quota SSH command, timer, retry, fallback
scan, `df`, `du`, or `find`. Do not copy a quota command from another HPC
center. Do not present a status command such as TRUBA's `lssrv` as quota.
TRUBA documents storage but keeps automated quota disabled because no verified
automated quota command was available for its published release.

### Scheduler command placeholders

Scheduler/job commands support `{user}`, `{job_id}`, `{job_id_q}`,
`{script_dir}`, `{script_dir_q}`, `{script_name}`, and `{script_name_q}`.
The `_q` forms are quoted shell arguments and should be preferred for paths,
IDs, and names.

### Quota command placeholders

Quota fields use their separate allow-list: `{user}`, `{subject}`, `{path}`,
and `{path_q}`. Unknown placeholders and multiline command templates are
rejected where the validator applies those rules. All provider commands must
be read-only and safe; destructive commands and executable hooks are
prohibited.

## Publish the package and registry entry

Move the finished staging directory to:

```text
plugins/example/0.1.0/
├── manifest.json
├── cluster-profile.json
└── README.md
```

There is no separate packaging command: the version directory is the package.
Every file must be declared in `manifest.json`. Add a `registry.json` entry
whose required fields mirror the live schema:

```json
{"id": "org.hpcclient.example", "name": "Example University HPC",
 "version": "0.1.0", "plugin_api": 1, "type": "cluster-profile",
 "description": "Cluster profile for Example University HPC.",
 "publisher": "Example University HPC contributor", "requires_app": ">=1.5.5",
 "manifest_path": "plugins/example/0.1.0/manifest.json",
 "manifest_sha256": "<64 lowercase hex characters>", "official": false,
 "capabilities": ["cluster-profile"]}
```

Run `python scripts/refresh_hashes.py` after placing the package and registry
entry. It updates payload size/SHA-256 values in manifests and manifest hashes
in the registry. The chain is `registry → manifest → provider files`; SHA-256
verifies repository/package integrity, not publisher identity or a signature.

Published versions are immutable. Never edit `plugins/example/0.1.0/` after
publication; create `plugins/example/0.1.1/` (or another semantic version),
add its registry entry, and leave the old version intact for rollback.

## Validate before the pull request

```bash
python scripts/validate_registry.py
python -m pytest
ruff check scripts tests
```

The validator checks schemas, identity, compatibility, safe paths, declared
files, sizes, hashes, entrypoints, payload roles, immutable directories, and
placeholder rules. Tests cover registry/tooling behavior. Ruff checks the
Python tooling. `python -m ruff check scripts tests` is equivalent when Ruff
is installed as a module.

## What can safely be left blank?

| Field | Can be blank? | Result |
| --- | ---: | --- |
| Documentation URL | Yes | No documentation link shown |
| Scratch path | Yes | Scratch area is not advertised |
| Project path | Yes | No project storage card |
| Partition list | Yes | No site-specific partition hints |
| Software notes | Yes | No extra software guidance |
| Quota command | Yes | No quota query is performed |

Partial but verified provider data is better than complete but guessed data.

## Common mistakes

- Guessing `/scratch/{user}` because another center uses it. Use only a
  documented or confirmed path.
- Copying another site's quota command. Do not do this.
- Adding usernames, passwords, SSH keys, tokens, private hostnames, VPN
  secrets, or personally assigned accounts.
- Hardcoding a personal project or account value instead of site-level public
  guidance.
- Editing an already published version instead of making a new version.
- Forgetting registry hashes; run the refresh and validation scripts.
- Treating TRUBA as a universal template. It is one provider example.

## Pull request checklist

```text
[ ] New provider version directory added
[ ] Manifest, cluster profile, and README validate
[ ] Registry entry added and hashes refreshed
[ ] Public sources linked for paths, partitions, policies, and commands
[ ] No credentials, private data, or guessed quota command
[ ] No existing published version modified
[ ] python scripts/validate_registry.py passes
[ ] python -m pytest passes
[ ] ruff check scripts tests passes
```

```bash
git add .
git commit -m "Add Example University HPC provider"
git push origin add-example-university-provider
```

Open a pull request from your fork against the plugin registry repository.
Reviewers may request sources for storage paths, partitions, scheduler
commands, quota commands, and public policy details.

## After merge

Users install the published provider locally through:

```text
HPC Client GUI → Plugins → Discover → <Provider> → Install
```

Installation downloads and verifies the package on the local machine; nothing
is installed on the HPC server. The profile appears under
`System Templates → Installed Plugins`. Applying it supplies defaults that a
user may edit for their connection. Those overrides stay local.

For an update, create a new immutable version directory, update the registry,
refresh hashes, validate, and open another pull request. Existing versions
remain available for rollback.

## End-to-end Example University HPC checklist

1. Fork the repository and create `add-example-university-provider`.
2. Run the scaffolder command above.
3. Open `cluster-profile.json` and add only verified Home, Scratch, and docs data.
4. Leave quota disabled because no verified command exists.
5. Move the package to `plugins/example/0.1.0/` and add the registry entry.
6. Run `python scripts/refresh_hashes.py`.
7. Run `python scripts/validate_registry.py`, `python -m pytest`, and `ruff check scripts tests`.
8. Commit, push, and open the pull request.
