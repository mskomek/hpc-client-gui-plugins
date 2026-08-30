# Cluster profile field guide

Use `schema/cluster-profile.schema.json` as the authority. A profile must have
`schema_version`, `profile_id`, `name`, and `scheduler`; new profiles should
use schema v2 and `scheduler: "slurm"`.

| Field | Required? | Meaning |
| --- | --- | --- |
| `schema_version` | Yes | Profile schema generation (`2` for structured storage). |
| `profile_id` | Yes | Stable lowercase internal ID. |
| `name` | Yes | User-facing provider name. |
| `scheduler` | Yes | Supported scheduler, currently `slurm`. |
| `metadata` | Optional | Public maintainer and HTTPS documentation/support URLs. |
| `site` | Optional | Public name, region, access note, and docs URL. |
| `scheduler_hints` | Optional | Verified queue, account, and partition guidance. |
| `software` | Optional | Module paths and plain-language setup notes. |
| `storage` | Optional | Known filesystem areas; omit unknown areas. |
| `quota_sources` | Optional | Explicitly reviewed quota integrations only. |

`paths` and `commands` remain available for compatibility with the app's
standard Slurm settings. Command templates may use only the placeholders
documented in the provider tutorial; quote `_q` values and never add
destructive commands or executable hooks.

## Storage entries

Each storage row requires `id` and `label`. `kind` is normally `home`,
`scratch`, `project`, `custom`, or `node-local`; `enabled` controls whether it
is advertised. `path_template` is the documented path and may contain
`{user}`. `access_context` describes where it is reachable, such as `login`.

`policy.backup` is a verified backup statement. `policy.retention_days` is a
verified non-negative number of days, or `null` when unknown. Do not guess
either value. Other useful policy fields include `cleanup_note`,
`documentation_url`, and `source_refs`.

## Quota entries

Quota is optional and separate from storage. A quota row has an `id` and may
include `enabled`, `backend_id`, `command_template`, and `scope`. A blank or
disabled command must remain disabled: the app performs no quota request,
probe, timer, retry, `df`, `du`, or `find` fallback. Never copy a quota command
from another site.
