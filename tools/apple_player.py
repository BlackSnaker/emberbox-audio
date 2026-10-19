#!/usr/bin/env python3
"""Configure an installed DRM-capable runtime for Emberbox's Apple Music player."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from paths import CONFIG_DIR


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True, help='Compatible installed Electron/Chromium executable')
    parser.add_argument('--widevine', type=Path, required=True, help='Installed Widevine version directory containing manifest.json')
    parser.add_argument('--profile', type=Path, default=CONFIG_DIR/'apple-web-profile', help='Emberbox-owned Apple Music profile')
    args = parser.parse_args()
    runtime, module = args.runtime.expanduser().resolve(), args.widevine.expanduser().resolve()
    if not runtime.is_file() or not os.access(runtime, os.X_OK):
        parser.error('The runtime must be an installed executable.')
    if not (module/'manifest.json').is_file() or not (module/'_platform_specific/linux_x64/libwidevinecdm.so').is_file():
        parser.error('The Widevine directory needs manifest.json and the Linux x64 module.')
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path = CONFIG_DIR/'apple-engine.json'
    path.write_text(json.dumps({'runtime':str(runtime),'cdm_module':str(module),
                                'profile':str(args.profile.expanduser().resolve())},indent=2)+'\n')
    path.chmod(0o600)
    print('Configured Apple Music. Select Apple Music in Emberbox, then sign in if prompted.')


if __name__ == '__main__':
    main()
