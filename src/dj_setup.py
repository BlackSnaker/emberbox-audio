"""Optional app-owned voice/brain assets: bounded downloads, pinned hashes, no sudo."""
import fcntl,hashlib,json,os,platform,shutil,stat,subprocess,sys,tarfile,threading,time,venv,zipfile
from pathlib import Path
import urllib.request
from paths import CACHE_DIR
from karaoke_model import _download

ROOT=Path(os.environ.get('EMBERBOX_DJ_DIR',CACHE_DIR/'ember-dj'))
VOICE_REV='5041a7a49ae5b3a0f30e6837769eb03fdbb231bd'
VOICE_BASE='https://huggingface.co/rhasspy/piper-voices/resolve/'+VOICE_REV+'/'
MODEL_NAME='qwen2.5-1.5b-instruct-q4_k_m.gguf'
ASSETS={
 'piper':('https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_amd64.tar.gz',
    '467c17935d2a22dcce9dc9e08ba07485e29be813097e7cf08c5627aa09d32e42',25916047,'piper.tar.gz'),
 'asr-ru':('https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip',
    '961d5ff98a17f4aa6de69864d0aa71fa5bac682301d2b5d17a3f24c5c99a46d4',46236750,'asr-ru.zip'),
 'tts-ru':(VOICE_BASE+'ru/ru_RU/denis/medium/ru_RU-denis-medium.onnx',
    '15fab56e11a097858ee115545d0f697fc2a316c41a291a5362349fb870411b0a',63201294,'ru_RU-denis-medium.onnx'),
 'tts-ru-config':(VOICE_BASE+'ru/ru_RU/denis/medium/ru_RU-denis-medium.onnx.json',
    '831c860dac0b5073eaa81610a0a638ec23d90a6cf8e5f871b4485c2cec3767c8',4823,'ru_RU-denis-medium.onnx.json'),
 'asr-en':('https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip',
    '30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498',41205931,'asr-en.zip'),
 'tts-en':(VOICE_BASE+'en/en_US/joe/medium/en_US-joe-medium.onnx',
    '58afce0321b8d9c46d7cdf9c16500cc55a793b4220212dba6b70fb788b3baf06',63201294,'en_US-joe-medium.onnx'),
 'tts-en-config':(VOICE_BASE+'en/en_US/joe/medium/en_US-joe-medium.onnx.json',
    '3d6d5410b3795cb1950595247ef8f06190719e6fdbfa3a2356d8ec368e1aad33',4794,'en_US-joe-medium.onnx.json'),
 'llama':('https://github.com/ggml-org/llama.cpp/releases/download/b11838/llama-b11838-bin-ubuntu-x64.tar.gz',
    '507e2f4fe3553499b518efe74a4244e35d709154a4e51c67e3affeef228ceb30',22349871,'llama.tar.gz'),
 'brain':('https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/'+MODEL_NAME,
    '6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e',1117320736,MODEL_NAME)}
VOICES={'ru':'ru_RU-denis-medium','en':'en_US-joe-medium'}


def ready(kind='voice',language='ru'):
    try:
        data=json.loads((ROOT/('brain.json' if kind=='brain' else kind+'-'+language+'.json')).read_text())
        if data.get('version')!=1:return False
        if kind=='brain':return (ROOT/'llama/llama-server').is_file() and (ROOT/MODEL_NAME).stat().st_size==ASSETS['brain'][2]
        return Path(data['python']).is_file() and (ROOT/'piper/piper').is_file() and (ROOT/('asr-'+language)/'am/final.mdl').is_file() and (ROOT/(VOICES[language]+'.onnx')).stat().st_size==ASSETS['tts-'+language][2]
    except (OSError,ValueError,TypeError,KeyError):return False


def safe_unpack(archive,destination,max_bytes=500_000_000):
    """No absolute paths, traversal, device files, escaping links or zip bombs."""
    root=Path(destination).resolve();root.mkdir(parents=True,exist_ok=True,mode=0o700)
    def path(name):
        p=(root/name).resolve()
        if p==root or not p.is_relative_to(root):raise ValueError('Unsafe archive path')
        return p
    total=0
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                p=path(info.filename);total+=info.file_size
                if total>max_bytes or stat.S_ISLNK(info.external_attr>>16):raise ValueError('Unsafe model archive')
                if info.is_dir():p.mkdir(parents=True,exist_ok=True,mode=0o700);continue
                p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                with z.open(info) as source,p.open('wb') as output:shutil.copyfileobj(source,output)
                p.chmod(0o600)
    else:
        with tarfile.open(archive) as tar:
            for info in tar:
                p=path(info.name);total+=max(0,info.size)
                if total>max_bytes:raise ValueError('Runtime archive too large')
                if info.isdir():p.mkdir(parents=True,exist_ok=True,mode=0o700);continue
                p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                if info.issym():
                    target=(p.parent/info.linkname).resolve()
                    if not target.is_relative_to(root):raise ValueError('Unsafe runtime link')
                    p.symlink_to(info.linkname)
                elif info.isfile():
                    with tar.extractfile(info) as source,p.open('wb') as output:shutil.copyfileobj(source,output)
                    p.chmod(0o700 if info.mode&0o111 else 0o600)
                else:raise ValueError('Unsupported runtime archive entry')


def asset(name,progress,stop):
    url,sha,size,filename=ASSETS[name];path=ROOT/filename
    valid=False
    if path.is_file() and path.stat().st_size==size:
        digest=hashlib.sha256()
        with path.open('rb') as f:
            while chunk:=f.read(1024*1024):
                if stop.is_set():raise InterruptedError('cancelled')
                digest.update(chunk)
        valid=digest.hexdigest()==sha
    if not valid:_download(url,path,sha,size,lambda fraction:progress(name,fraction),stop)
    return path


def runtime(progress,stop):
    python=ROOT/'runtime/bin/python'
    if python.is_file():
        if subprocess.run([str(python),'-I','-c','import vosk'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15).returncode==0:return python
    progress('runtime',0.)
    build=ROOT/'runtime-next'
    if build.exists():shutil.rmtree(build)
    venv.EnvBuilder(with_pip=False,system_site_packages=True).create(build)
    executable=build/'bin/python';bootstrap=ROOT/'pip-bootstrap.whl'
    with urllib.request.urlopen('https://pypi.org/pypi/pip/25.3/json',timeout=15) as r:data=json.loads(r.read(500000))
    wheel=next(x for x in data['urls'] if x['filename'].endswith('py3-none-any.whl'))
    _download(wheel['url'],bootstrap,wheel['digests']['sha256'],4_000_000,lambda _:None,stop)
    code='import sys,runpy;sys.path.insert(0,sys.argv.pop(1));runpy.run_module("pip",run_name="__main__")'
    command=[str(executable),'-I','-c',code,str(bootstrap),'install','--isolated','--disable-pip-version-check',
             '--no-input','--index-url','https://pypi.org/simple','vosk==0.3.45']
    with (ROOT/'setup.log').open('w') as log:
        os.chmod(ROOT/'setup.log',0o600)
        process=subprocess.Popen(command,stdout=log,stderr=log)
        try:
            deadline=time.monotonic()+240
            while process.poll() is None:
                if stop.wait(.1):raise InterruptedError('cancelled')
                if time.monotonic()>deadline:raise TimeoutError('Voice runtime setup timed out')
            if process.returncode:raise RuntimeError('voice-runtime-install')
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=2)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
    subprocess.run([str(executable),'-I','-c','import vosk'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
    target=ROOT/'runtime'
    if target.exists():shutil.rmtree(target)
    build.replace(target);bootstrap.unlink(missing_ok=True)
    return python


def prepare(kind='voice',language='ru',progress=lambda *_:None,stop=None):
    stop=stop or threading.Event()
    if kind not in ('voice','brain') or language not in VOICES:raise ValueError('Unsupported DJ component')
    if platform.machine().lower() not in ('x86_64','amd64'):raise RuntimeError('Local DJ models currently require Linux x86_64')
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (ROOT/'setup.lock').open('a') as lock:
        while True:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if stop.wait(.15):raise InterruptedError('cancelled')
        names=('llama','brain') if kind=='brain' else ('piper','asr-'+language,'tts-'+language,'tts-'+language+'-config')
        for name in names:
            if stop.is_set():raise InterruptedError('cancelled')
            path=asset(name,progress,stop)
            if name in ('piper','llama') or name.startswith('asr-'):
                destination=ROOT/(name+'-next')
                if destination.exists():shutil.rmtree(destination)
                safe_unpack(path,destination)
                contents=list(destination.iterdir())
                if len(contents)!=1 or not contents[0].is_dir():raise ValueError('Unexpected model archive')
                target=ROOT/name
                if target.exists():shutil.rmtree(target)
                contents[0].replace(target);destination.rmdir()
        python=runtime(progress,stop) if kind=='voice' else ''
        if stop.is_set():raise InterruptedError('cancelled')
        marker=ROOT/('brain.json' if kind=='brain' else kind+'-'+language+'.json');temporary=marker.with_suffix('.next')
        temporary.write_text(json.dumps({'version':1,'python':str(python)}));temporary.chmod(0o600);temporary.replace(marker)
        progress('ready',1.)
