#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export GDK_BACKEND=x11
exec "${EMBERBOX_PYTHON:-python3}" "$project_dir/src/widget.py" "$@"
