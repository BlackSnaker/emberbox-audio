"""Discover and validate local playback components without reading account data."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from paths import CONFIG_DIR

ENGINE_CONFIG = CONFIG_DIR/'apple-engine.json'


class SetupError(RuntimeError):
    pass


def valid(config):
    try:
        runtime = Path(config['runtime'])
        module = Path(config['cdm_module'])
        return runtime.is_file() and os.access(runtime,os.X_OK) and \
            (module/'manifest.json').is_file() and (module/'_platform_specific/linux_x64/libwidevinecdm.so').is_file()
    except (KeyError,TypeError):
        return False


def configured(config_path=None):
    try:
        value = json.loads((config_path or ENGINE_CONFIG).read_text())
        return value if valid(value) else None
    except (OSError,ValueError):
        return None


def runtime_candidates():
    values = [os.environ.get('EMBERBOX_APPLE_RUNTIME',''),shutil.which('electron') or '',
              '/usr/lib/chatgpt/ChatGPT']
    values += [str(path) for path in Path('/usr/lib').glob('electron*/electron')]
    return list(dict.fromkeys(str(Path(value).expanduser().resolve()) for value in values
                             if value and Path(value).expanduser().is_file()))[:4]


def widevine_candidates():
    home = Path.home()
    config = Path(os.environ.get('XDG_CONFIG_HOME',home/'.config'))
    roots = [config/'Codex/WidevineCdm',config/'google-chrome/WidevineCdm',
             config/'chromium/WidevineCdm',config/'BraveSoftware/Brave-Browser/WidevineCdm',
             Path('/opt/google/chrome/WidevineCdm'),Path('/usr/lib/chromium/WidevineCdm')]
    override = os.environ.get('EMBERBOX_APPLE_WIDEVINE')
    values = [Path(override).expanduser()] if override else []
    # Enumerate only installed public module directories, never browser stores.
    for root in roots:
        values.append(root)
        if root.is_dir():
            values.extend(sorted((p for p in root.iterdir() if p.is_dir()),reverse=True)[:10])
    return [str(p.resolve()) for p in values if (p/'manifest.json').is_file()
            and (p/'_platform_specific/linux_x64/libwidevinecdm.so').is_file()]


def save(config, config_path=None):
    destination = config_path or ENGINE_CONFIG
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary = destination.with_suffix('.next.json')
    with open(temporary,'w',opener=lambda path,flags:os.open(path,flags,0o600)) as stream:
        json.dump(config,stream,indent=2)
        stream.write('\n')
    temporary.chmod(0o600)
    temporary.replace(destination)


def prepare(runtime=None, module=None, *, config_path=None, profile_name='apple-web-profile'):
    existing = configured(config_path)
    if existing and not runtime and not module:
        return existing
    runtimes = [str(Path(runtime).expanduser().resolve())] if runtime else runtime_candidates()
    modules = [str(Path(module).expanduser().resolve())] if module else widevine_candidates()
    if not runtimes:
        raise SetupError('NEEDS_ENGINE')
    if not modules:
        raise SetupError('NEEDS_DRM')
    for candidate in runtimes:
        for cdm in modules[:2]:
            config = {'runtime':candidate,'cdm_module':cdm,
                      'profile':(existing or {}).get('profile',str(CONFIG_DIR/profile_name))}
            if not valid(config):
                continue
            try:
                result = subprocess.run([sys.executable,str(Path(__file__).with_name('apple_engine_launcher.py')),
                                         '--runtime',candidate,'--cdm-module',cdm,'--probe'],
                                        capture_output=True,text=True,timeout=40)
                reports = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{"engine":')]
                capabilities = reports[-1].get('capabilities',{}) if reports else {}
                if result.returncode == 0 and capabilities.get('aac') and capabilities.get('widevine') and capabilities.get('mediaKeysCreated'):
                    save(config,config_path)
                    return config
            except (OSError,ValueError,subprocess.SubprocessError):
                continue
    raise SetupError('INCOMPATIBLE_ENGINE')
