#!/usr/bin/env python3
"""Build, opt in, pair and open Ember Quest through a local USB reverse tunnel."""
import argparse,json,os,platform,shutil,subprocess,sys,tempfile,time,zipfile
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]
CACHE=Path(os.environ.get('XDG_CACHE_HOME',Path.home()/'.cache'))/'emberbox-audio'/'quest-tools'


def run(args,**options):return subprocess.run([str(v) for v in args],check=True,**options)

def adb():
    system=shutil.which('adb')
    if system:return Path(system)
    binary=CACHE/'platform-tools'/'adb'
    if binary.exists():return binary
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','amd64'):raise RuntimeError('Install Android platform-tools for this computer first')
    CACHE.mkdir(parents=True,exist_ok=True)
    archive=CACHE/'platform-tools.zip'
    print('Downloading Android platform-tools from Google…')
    with urlopen('https://dl.google.com/android/repository/platform-tools-latest-linux.zip',timeout=90) as response,archive.open('wb') as out:shutil.copyfileobj(response,out)
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            if not (CACHE/member.filename).resolve().is_relative_to(CACHE.resolve()):raise RuntimeError('Invalid platform-tools archive')
        bundle.extractall(CACHE)
    binary.chmod(0o755);return binary

def service_name(preferred=None):
    if preferred:return preferred
    for name in ('emberbox-audio.service','gruvbox-spotify-widget.service'):
        result=subprocess.run(['systemctl','--user','show',name,'-p','MainPID','--value'],capture_output=True,text=True)
        if result.stdout.strip().isdigit() and int(result.stdout.strip())>0:return name
    raise RuntimeError('Start the installed Ember desktop player first, or specify --service')

def player_folder(service,chosen=None):
    if chosen:return Path(chosen).expanduser().resolve()
    pid=subprocess.check_output(['systemctl','--user','show',service,'-p','MainPID','--value'],text=True).strip()
    for argument in Path('/proc',pid,'cmdline').read_bytes().split(b'\0'):
        if argument.endswith(b'/widget.py'):return Path(os.fsdecode(argument)).parent
    raise RuntimeError('Cannot locate the running desktop player; use --player-dir')

def build():
    if not shutil.which('npm'):raise RuntimeError('Node.js and npm are required to build Quest assets')
    run(['npm','--prefix',ROOT/'quest','ci','--ignore-scripts'])
    run(['npm','--prefix',ROOT/'quest','run','build'])

def install(args):
    build();service=service_name(args.service);target=player_folder(service,args.player_dir);widget=target/'widget.py'
    text=widget.read_text();backup=Path(tempfile.mkdtemp(prefix='before-quest-',dir=None));backup.chmod(0o700);shutil.copy2(widget,backup/'widget.py')
    if 'start_quest_bridge' not in text:
        anchors=('from widget_control import WidgetControl','        self.widget_control=WidgetControl(self.show_widget,self.hide_widget,self.quit)','        self.resources_closed = True\n        self.music.close()')
        if any(text.count(a)!=1 for a in anchors):raise RuntimeError('This player version needs an explicit integration update; no files changed')
        text=text.replace(anchors[0],anchors[0]+'\nfrom quest_bridge import start_if_enabled as start_quest_bridge').replace(anchors[1],anchors[1]+'\n        self.quest_bridge=start_quest_bridge(self)').replace(anchors[2],"        self.resources_closed = True\n        if getattr(self,'quest_bridge',None):self.quest_bridge.close()\n        self.music.close()")
    compile(text,str(widget),'exec')
    run(['systemctl','--user','stop',service])
    try:
        shutil.copytree(ROOT/'quest'/'dist',target/'quest-web',dirs_exist_ok=True)
        shutil.copy2(ROOT/'src'/'quest_bridge.py',target/'quest_bridge.py')
        temp=widget.with_suffix('.quest-tmp');temp.write_text(text);temp.chmod(widget.stat().st_mode&0o777);temp.replace(widget)
        folder=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'systemd'/'user'/(service+'.d');folder.mkdir(parents=True,exist_ok=True)
        value=str(target/'quest-web').replace('%','%%').replace('\\','\\\\').replace('"','\\"')
        (folder/'quest.conf').write_text('[Service]\nEnvironment=EMBERBOX_QUEST=1\nEnvironment=EMBERBOX_QUEST_ORIGIN=https://blacksnaker.github.io\nEnvironment="EMBERBOX_QUEST_WEB='+value+'"\n')
        run(['systemctl','--user','daemon-reload'])
    finally:run(['systemctl','--user','start',service])
    print('Companion enabled on localhost only. Private backup:',backup)

def pairing():
    folder=Path(os.environ.get('XDG_RUNTIME_DIR',Path(os.environ.get('XDG_CACHE_HOME',Path.home()/'.cache'))/'emberbox-audio'))/'emberbox-audio'
    path=folder/'quest-pair.json'
    for _ in range(50):
        try:return json.loads(path.read_text())
        except (OSError,ValueError):time.sleep(.1)
    raise RuntimeError('Quest companion is not running. Run install-companion first.')

def open_room(app=False):
    binary=adb();result=subprocess.check_output([binary,'devices'],text=True)
    if 'unauthorized' in result:raise RuntimeError('Confirm USB debugging inside your Quest, then repeat open')
    if not any(line.endswith('\tdevice') for line in result.splitlines()):raise RuntimeError('Connect and unlock the Quest over USB first')
    pair=pairing();run([binary,'reverse',f"tcp:{pair['port']}",f"tcp:{pair['port']}"],stdout=subprocess.DEVNULL)
    url=pair['url'].replace('/#','/?build='+str(int(time.time()))+'#')
    command=[binary,'shell','am','start','-a','android.intent.action.VIEW','-d',url]
    if app:
        url='https://blacksnaker.github.io/?build='+str(int(time.time()))+'#pair='+pair['url'].split('#pair=',1)[1]
        command=[binary,'shell','am','start','-n','io.emberbox.quest/.LauncherActivity','-a','android.intent.action.VIEW','-d',url]
    run(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print('Ember Quest app opened and paired.' if app else 'Ember opened on Quest. Press «Войти в комнату» in the headset, then connect audio explicitly.')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('build','install-companion','open','open-app','install-app','disable'));parser.add_argument('--service');parser.add_argument('--player-dir');parser.add_argument('--apk',type=Path);args=parser.parse_args()
    try:
        if args.action=='build':build()
        elif args.action=='install-companion':install(args)
        elif args.action=='open':open_room()
        elif args.action=='open-app':open_room(app=True)
        elif args.action=='install-app':
            if not args.apk or not args.apk.is_file():raise RuntimeError('Pass --apk /path/to/Ember-Quest.apk')
            run([adb(),'install','-r',str(args.apk.resolve())]);open_room(app=True)
        else:
            service=service_name(args.service);file=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'systemd'/'user'/(service+'.d')/'quest.conf';file.unlink(missing_ok=True);run(['systemctl','--user','daemon-reload']);run(['systemctl','--user','restart',service]);print('Quest companion disabled; desktop playback engine kept installed.')
    except (OSError,RuntimeError,subprocess.CalledProcessError) as exc:parser.exit(1,str(exc)+'\n')

if __name__=='__main__':main()
