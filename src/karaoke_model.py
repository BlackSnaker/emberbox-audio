"""Optional private AI runtime and verified UVR weights; no music leaves the PC."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import venv
from paths import CACHE_DIR

ROOT=Path(os.environ.get('EMBERBOX_KARAOKE_AI_DIR',CACHE_DIR/'karaoke-ai'))
MODEL_NAME='UVR_MDXNET_9482.onnx'
MODEL_SHA='f4f365207c56deb115bceedff3ad8fe98a751c745f9e370cecec6226b8b47184'
MODEL_SIZE=29704436
MODEL_URL='https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/'+MODEL_NAME
MODEL=ROOT/MODEL_NAME
PYTHON=ROOT/'runtime/bin/python'
STAMP=ROOT/'ready.json'


def ready():
    try:
        data=json.loads(STAMP.read_text())
        return PYTHON.is_file() and MODEL.stat().st_size==MODEL_SIZE and data.get('sha256')==MODEL_SHA and data.get('version')==1
    except (OSError,ValueError):return False


def verified_model():
    if MODEL.stat().st_size!=MODEL_SIZE or hashlib.sha256(MODEL.read_bytes()).hexdigest()!=MODEL_SHA:
        raise RuntimeError('ai-model-invalid')
    return MODEL


def _download(url,path,expected,limit,progress,stop):
    request=urllib.request.Request(url,headers={'User-Agent':'Emberbox-Audio karaoke setup'})
    temporary=path.with_suffix(path.suffix+'.part')
    digest=hashlib.sha256();total=0;last=0.
    try:
        with urllib.request.urlopen(request,timeout=20) as source,temporary.open('wb') as output:
            os.chmod(temporary,0o600)
            while chunk:=source.read(256*1024):
                if stop.is_set():raise InterruptedError('cancelled')
                total+=len(chunk)
                if total>limit:raise ValueError('Download exceeds limit')
                output.write(chunk);digest.update(chunk)
                if time.monotonic()-last>.25:
                    progress(min(1,total/limit));last=time.monotonic()
        if digest.hexdigest()!=expected:raise ValueError('Download checksum mismatch')
        temporary.replace(path)
    finally:temporary.unlink(missing_ok=True)


def prepare(progress=lambda *_:None,stop=None):
    stop=stop or threading.Event()
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (ROOT/'setup.lock').open('a') as lock:
        os.chmod(ROOT/'setup.lock',0o600)
        while True:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if stop.wait(.2):raise InterruptedError('cancelled')
        try:model_ok=bool(verified_model())
        except (OSError,RuntimeError):model_ok=False
        if not model_ok:
            progress('download',0.)
            _download(MODEL_URL,MODEL,MODEL_SHA,MODEL_SIZE,lambda fraction:progress('download',fraction),stop)
        runtime_ok=False
        if PYTHON.is_file():
            progress('runtime',0.)
            try:
                runtime_ok=subprocess.run([str(PYTHON),'-I','-c','import numpy,scipy,onnx,onnxruntime'],
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=25).returncode==0
            except (OSError,subprocess.SubprocessError):pass
        if not runtime_ok:
            progress('runtime',0.)
            build=ROOT/'runtime-next'
            if build.exists():shutil.rmtree(build)
            venv.EnvBuilder(with_pip=False,system_site_packages=True).create(build)
            executable=build/'bin/python'
            bootstrap=ROOT/'pip-bootstrap.whl'
            # Bootstrap pip inside the venv even on systems without ensurepip.
            # PyPI supplies the versioned wheel's SHA256 over TLS, as pip does.
            with urllib.request.urlopen('https://pypi.org/pypi/pip/25.3/json',timeout=15) as response:
                info=json.loads(response.read(500000))
            wheel=next(item for item in info['urls'] if item['filename'].endswith('py3-none-any.whl'))
            _download(wheel['url'],bootstrap,wheel['digests']['sha256'],4_000_000,lambda _:None,stop)
            old=sys.version_info<(3,11)
            requirements=['onnxruntime=='+('1.20.1' if old else '1.31.0'),
                          'onnx=='+('1.17.0' if old else '1.21.0'),'scipy>=1.10,<2']
            code='import sys,runpy;sys.path.insert(0,sys.argv.pop(1));runpy.run_module("pip",run_name="__main__")'
            command=[str(executable),'-I','-c',code,str(bootstrap),'install','--isolated',
                     '--disable-pip-version-check','--only-binary=:all:','--no-input',
                     '--index-url','https://pypi.org/simple',*requirements]
            with (ROOT/'setup.log').open('w') as log:
                os.chmod(ROOT/'setup.log',0o600)
                process=subprocess.Popen(command,stdout=log,stderr=log)
                try:
                    deadline=time.monotonic()+360
                    while process.poll() is None:
                        if stop.wait(.15):raise InterruptedError('cancelled')
                        if time.monotonic()>deadline:raise TimeoutError('Runtime setup timed out')
                    if process.returncode:raise RuntimeError('ai-runtime-install')
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:process.wait(timeout=2)
                        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
            if stop.is_set():raise InterruptedError('cancelled')
            subprocess.run([str(executable),'-I','-c','import numpy,scipy,onnx,onnxruntime'],check=True,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
            old_runtime=ROOT/'runtime-old'
            if old_runtime.exists():shutil.rmtree(old_runtime)
            if (ROOT/'runtime').exists():(ROOT/'runtime').replace(old_runtime)
            try:build.replace(ROOT/'runtime')
            except OSError:
                if old_runtime.exists():old_runtime.replace(ROOT/'runtime')
                raise
            if old_runtime.exists():shutil.rmtree(old_runtime)
            bootstrap.unlink(missing_ok=True)
        if stop.is_set():raise InterruptedError('cancelled')
        verified_model()
        temporary=STAMP.with_suffix('.next')
        with temporary.open('w') as output:
            os.chmod(temporary,0o600);json.dump({'version':1,'sha256':MODEL_SHA},output)
        temporary.replace(STAMP)
        progress('ready',1.)


if __name__=='__main__' and '--prepare' in sys.argv:
    stopped=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:stopped.set())
    def watch_parent():
        while not stopped.is_set():
            try:
                if select.select([sys.stdin],[],[],.3)[0] and not os.read(sys.stdin.fileno(),1):stopped.set()
            except (OSError,ValueError):stopped.set()
    # CLI is also useful for packaging/diagnostics; only GUI launches watch EOF.
    if '--watch-parent' in sys.argv:threading.Thread(target=watch_parent,daemon=True).start()
    def emit(stage,fraction):print(json.dumps({'stage':stage,'fraction':fraction}),flush=True)
    try:prepare(emit,stopped)
    except Exception as error:
        print(json.dumps({'stage':'error','error':'cancelled' if stopped.is_set() else 'ai-setup-failed'}),flush=True)
        raise SystemExit(1)
