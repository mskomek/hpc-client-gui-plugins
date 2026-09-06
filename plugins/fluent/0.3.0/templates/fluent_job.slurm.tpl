#!/bin/bash
#SBATCH --partition={{partition}}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task={{cpus}}
#SBATCH --time={{time_limit}}
#SBATCH --output={{journal_base}}.o%j

# Static template provided by the Fluent Journal Lint plugin.
# Review every value before submitting; nothing is executed until you do.
#
# Add your cluster-specific environment setup here (for example the
# module/command that exposes Fluent on your system), then adjust the
# launch command below if your site uses a different executable path.

fluent 3ddp -g -t{{cpus}} -i {{journal_file}} > {{journal_base}}.log 2>&1
