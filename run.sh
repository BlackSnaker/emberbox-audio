#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ember_data="${XDG_DATA_HOME:-$HOME/.local/share}/emberbox-audio"
if [ -n "${EMBERBOX_PYTHON:-}" ]; then
    ember_python=$EMBERBOX_PYTHON
else
    ember_base=$(command -v python3)
    ember_python=$("$ember_base" -B - "$ember_data/.emberbox-install.json" <<'PY'
import json,sys
from pathlib import Path
try:
    selected=json.loads(Path(sys.argv[1]).read_text()).get('python','')
    print(selected if selected and Path(selected).is_file() else sys.executable)
except (OSError,ValueError,TypeError):print(sys.executable)
PY
)
fi
export GDK_BACKEND=x11
export PATH="$(dirname -- "$ember_python"):$PATH"
exec "$ember_python" -B "$project_dir/src/widget.py" "$@"
