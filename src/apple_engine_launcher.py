#!/usr/bin/env python3
"""Run the Apple Music backend with a separate copy of an installed engine.

The vendor application and all of its account/profile files remain separate.
Runtime binaries are not included in the repository or distribution.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from asar_pack import pack

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runtime', type=Path, required=True, help='Installed Electron/Chromium executable.')
parser.add_argument('--cdm-module', type=Path, required=True, help='Installed Widevine version directory with manifest.json.')
parser.add_argument('--profile', type=Path, default=Path.home()/'.config/emberbox-audio/apple-chromium-experiment')
parser.add_argument('--socket', type=Path)
parser.add_argument('--visible', action='store_true')
parser.add_argument('--probe', action='store_true')
parser.add_argument('--smoke-seconds', type=int, default=0)
args = parser.parse_args()
source = args.runtime.resolve().parent
cdm_root = args.cdm_module.resolve()
cdm = cdm_root/'_platform_specific/linux_x64/libwidevinecdm.so'
manifest = json.loads((cdm_root/'manifest.json').read_text())
if not cdm.is_file():
    parser.error('Widevine module is missing its Linux x64 library.')
identity = str(args.runtime.resolve())+str(args.runtime.stat().st_mtime_ns)
cache = Path(os.environ.get('XDG_CACHE_HOME', Path.home()/'.cache'))/'emberbox-audio/apple-web-electron-runtime'/hashlib.sha256(identity.encode()).hexdigest()[:16]
cache.mkdir(parents=True, exist_ok=True, mode=0o700)
binary = cache/'EmberboxApple'
if not binary.exists() or binary.stat().st_mtime_ns != args.runtime.resolve().stat().st_mtime_ns:
    shutil.copy2(args.runtime.resolve(), binary)
for name in ('libGLESv2.so','libEGL.so','libvulkan.so.1','libvk_swiftshader.so','libffmpeg.so',
             'libqt5_shim.so','libqt6_shim.so','icudtl.dat','v8_context_snapshot.bin',
             'snapshot_blob.bin','resources.pak','chrome_100_percent.pak','chrome_200_percent.pak',
             'locales','vk_swiftshader_icd.json','browser_crashpad_handler','chrome-sandbox'):
    target = cache/name
    if (source/name).exists() and not target.exists():
        target.symlink_to(source/name)
(cache/'resources').mkdir(exist_ok=True)
pack(Path(__file__).resolve().parent/'apple_web_host',cache/'resources/app.asar')
temporary = tempfile.TemporaryDirectory(prefix='emberbox-chromium-check-', ignore_cleanup_errors=True) if args.probe or args.smoke_seconds else None
profile = Path(temporary.name) if temporary else args.profile.resolve()
profile.mkdir(parents=True, exist_ok=True, mode=0o700)
profile.chmod(0o700)
# Register only an installed public DRM module, never an existing browser session.
# Chromium on Linux reads this hint before starting its sandboxed renderers.
widevine = profile/'WidevineCdm'
widevine.mkdir(exist_ok=True)
(widevine/'latest-component-updated-widevine-cdm').write_text(json.dumps({'Path':str(cdm_root)}))
runtime = Path(os.environ.get('XDG_RUNTIME_DIR', tempfile.gettempdir()))/'emberbox-apple-web'
runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
env = dict(os.environ, EMBERBOX_APPLE_PROFILE=str(profile),
           EMBERBOX_APPLE_SOCKET=str(args.socket) if args.socket else '',
           EMBERBOX_APPLE_HIDE='0' if args.visible else '1',
           EMBERBOX_WIDEVINE=str(cdm), EMBERBOX_WIDEVINE_VERSION=manifest['version'],
           EMBERBOX_APPLE_PROBE='1' if args.probe else '0',
           EMBERBOX_APPLE_SMOKE_SECONDS=str(args.smoke_seconds),
           EMBERBOX_APPLE_STATUS=str(runtime/('electron-probe-status.json' if temporary else 'electron-status.json')))
command = [str(binary), '--class=emberbox-audio', '--disable-features=HardwareMediaKeyHandling',
           '--user-data-dir='+str(profile), '--widevine-cdm-path='+str(cdm),
           '--widevine-cdm-version='+manifest['version']]
try:
    # Some vendor runtimes mirror renderer console text to stderr themselves.
    # Keep raw website messages out of the journal; our app writes a strictly
    # sanitized status file. Disposable checks print our capability JSON only.
    result = subprocess.run(command, env=env, stderr=subprocess.DEVNULL,
                            stdout=subprocess.PIPE if temporary else subprocess.DEVNULL,
                            text=True)
    if temporary:
        for line in result.stdout.splitlines():
            if line.startswith('{"engine":'):
                print(line, flush=True)
finally:
    if temporary:
        temporary.cleanup()
raise SystemExit(result.returncode)
