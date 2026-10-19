#!/usr/bin/env python3
"""Register/remove the local Firefox native host; never edits browser profiles."""
import argparse
import json
from pathlib import Path
import shlex
import sys

HOST='org.emberbox.apple_music'
EXTENSION='apple-music@emberbox.local'
ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('install','uninstall'))
    parser.add_argument('--app',choices=('emberbox-audio','gruvbox-spotify-widget'),default='emberbox-audio')
    parser.add_argument('--host-script',type=Path,default=ROOT/'src/apple_native_host.py')
    parser.add_argument('--manifest-dir',type=Path,default=Path.home()/'.mozilla/native-messaging-hosts')
    args=parser.parse_args()
    manifest=args.manifest_dir/(HOST+'.json')
    wrapper=args.manifest_dir/'emberbox-apple-host'
    if manifest.exists():
        previous=json.loads(manifest.read_text())
        if previous.get('allowed_extensions')!=[EXTENSION] or previous.get('path')!=str(wrapper):
            parser.error('Refusing to overwrite an unmanaged native host')
    if args.action=='uninstall':
        if manifest.exists():
            manifest.unlink();wrapper.unlink(missing_ok=True)
        return 0
    if not args.host_script.exists():parser.error('Native host script is missing')
    args.manifest_dir.mkdir(parents=True,exist_ok=True)
    wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' '+shlex.quote(str(args.host_script.resolve()))+' --app '+shlex.quote(args.app)+' "$@"\n')
    wrapper.chmod(0o700)
    manifest.write_text(json.dumps({'name':HOST,'description':'Local Emberbox Apple Music library companion',
        'path':str(wrapper),'type':'stdio','allowed_extensions':[EXTENSION]},indent=2)+'\n')
    print('Registered Firefox native host. Load browser/apple-music/manifest.json as a temporary add-on.')
    print('No browser profile, cookies, passwords or signing settings were changed.')
    return 0


if __name__=='__main__':raise SystemExit(main())
