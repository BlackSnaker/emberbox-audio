#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$project_dir/tools/bootstrap.sh"
ember_bootstrap_python "$@"
exec "$EMBERBOX_BOOTSTRAP_PYTHON" -B "$project_dir/tools/install.py" install "$@"
