"""Prepare one silent public artwork clip before playback; bounded disk cache."""
import hashlib
from pathlib import Path
import subprocess
import time
import uuid
from paths import CACHE_DIR


CLIP_LIMIT=48*1024*1024
CACHE_LIMIT=160*1024*1024
MAX_AGE=7*86400


def cached_clip(executable,url,stop,process_changed,folder=None):
    folder=Path(folder) if folder else CACHE_DIR/'motion-clips'
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/(hashlib.sha256(url.encode()).hexdigest()+'.mp4')
    now=time.time()
    for path in folder.glob('*.part'):
        try:
            if now-path.stat().st_mtime>120:path.unlink(missing_ok=True)
        except FileNotFoundError:pass
    if target.is_file() and 0<target.stat().st_size<CLIP_LIMIT and now-target.stat().st_mtime<MAX_AGE:
        target.touch();return target.as_uri()
    files=[]
    for path in folder.glob('*.mp4'):
        try:
            info=path.stat();files.append((info.st_mtime,info.st_size,path))
        except FileNotFoundError:pass
    files.sort(reverse=True)
    total=0
    for modified,size,path in files:
        total+=size
        if total>CACHE_LIMIT-CLIP_LIMIT or now-modified>=MAX_AGE:
            path.unlink(missing_ok=True)
    temporary=folder/(target.stem+'.'+uuid.uuid4().hex+'.part')
    process=None
    try:
        # Download/remux once, without decoding or an audio stream. No network
        # request participates in the presentation clock or the next loop.
        command=[executable,'-nostdin','-loglevel','error','-protocol_whitelist','https,tls,tcp,crypto',
                 '-rw_timeout','7000000','-analyzeduration','1000000','-probesize','1000000',
                 '-i',url,'-map','0:v:0','-an','-sn','-dn','-c:v','copy',
                 '-fs',str(CLIP_LIMIT),'-f','mp4','-y',str(temporary)]
        if stop.is_set():return ''
        process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        process_changed(process)
        if stop.is_set():process.terminate();return ''
        code=process.wait(timeout=45)
        if code or stop.is_set() or not temporary.is_file() or not 0<temporary.stat().st_size<CLIP_LIMIT:return ''
        temporary.replace(target)
        return target.as_uri()
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=1)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        process_changed(None)
        temporary.unlink(missing_ok=True)
