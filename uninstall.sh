#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "${EMBERBOX_PYTHON:-python3}" "$project_dir/tools/install.py" uninstall "$@"
