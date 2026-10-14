# JSC JUWELS sources

## Access and account prerequisites
- https://apps.fz-juelich.de/jsc/hps/juwels/access.html — Cluster and Booster SSH endpoints, public-key setup through JuDoor, matching login endpoints for target modules, and optional JSC TOTP MFA.
- https://www.fz-juelich.de/en/jsc/services/user-support/how-to-get-access-to-systems/judoor — JuDoor account, project membership, and resource assignment process.

## Scheduler and hardware
- https://apps.fz-juelich.de/jsc/hps/juwels/batchsystem.html — Slurm, current Cluster and Booster partitions, default `batch` partition, development and large-job partition constraints, module-matched submission, and job-script guidance.
- https://apps.fz-juelich.de/jsc/hps/juwels/gpu-computing.html — Cluster `gpus` and Booster `booster` partitions and GPU request behavior.
- https://apps.fz-juelich.de/jsc/hps/juwels/configuration.html — JUWELS Cluster and Booster hardware and Slurm/ParaStation software overview.

## Environment and storage
- https://apps.fz-juelich.de/jsc/hps/juwels/environment.html — `$HOME`, `$PROJECT`, `$SCRATCH`, project activation via `jutil env activate`, and automatic scratch cleanup policy.
- https://apps.fz-juelich.de/jsc/hps/juwels/faq.html — filesystem purpose, backup notes, scratch cleanup, project/data storage, and quota query guidance.

## Limitations
- Partition names and system availability are documented snapshots; re-check the live JSC guide before use.
- Project membership, budget account, project-specific paths, host-key fingerprints, and quota values are not bundled.
- The profile is community-maintained data and is not an official JSC product.

## Last verified
- 2026-10-14 against the JSC pages linked above.
