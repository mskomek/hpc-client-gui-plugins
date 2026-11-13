# W65 review candidate 0.3.0-w65r17

This is a non-install-validated W65 source candidate. See W65_CANDIDATE.md before use.

## Inherited package documentation

# OpenFOAM Visual Case Studio 0.1.0

OpenFOAM.com / ESI v2312 case editor, validator, and draft-only workflow
builder. It edits selected dictionary files and creates a case-local `Allrun`
from the ordered workflow, using the application's SFTP adapter for remote
cases. The host Jobs flow includes a Slurm template for the
`apps/openfoam/v2312-2025` module; it loads OpenFOAM and runs `bash ./Allrun`.
It creates a script draft and never submits it. Existing `Allrun` files are
preserved. Interrupted remote-save recovery metadata is encrypted per saved
connection profile when host protected storage is available. Requires HPC
Client GUI 1.5.9 or newer. See the repository
[tool guide](../../../docs/OPENFOAM_CASE_STUDIO.md).

