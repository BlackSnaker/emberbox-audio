"""Run the native timing fixture with a temporary copy of an installed runtime."""
import json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from asar_pack import pack
repo=Path(__file__).resolve().parents[1]
installed=next((Path.home()/'.cache/emberbox-audio/apple-web-electron-runtime').glob('*/EmberboxApple'),None)
if not installed:raise SystemExit('Install the native Apple engine before this optional check.')
with tempfile.TemporaryDirectory(prefix='ember-beat-check-') as directory:
    root=Path(directory);binary=root/'EmberBeatCheck';shutil.copy2(installed,binary)
    for item in installed.parent.iterdir():
        if item.name not in ('resources',installed.name): (root/item.name).symlink_to(item)
    source=root/'source';source.mkdir();(root/'resources').mkdir()
    for name in ('package.json','main.cjs','page.js','yandex.js','media_quality.cjs','flow.cjs','rhythm.cjs','spatial.cjs','spatial_source.js'):
        if name=='main.cjs':shutil.copy2(repo/'tests/beat_engine_smoke.cjs',source/name)
        else:shutil.copy2(repo/'src/apple_web_host'/name,source/name)
    pack(source,root/'resources/app.asar')
    result=subprocess.run([str(binary),'--user-data-dir='+str(root/'profile')],capture_output=True,text=True,timeout=35)
    for line in result.stdout.splitlines():
        if 'beat_smoke' in line:print(line)
    if result.returncode:print(result.stderr[-3000:]);raise SystemExit(result.returncode)
