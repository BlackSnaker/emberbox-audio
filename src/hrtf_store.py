"""Private, content-addressed SOFA imports. Validate away from GTK/playback."""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from paths import CONFIG_DIR

ROOT=CONFIG_DIR/'hrtf'
LIMIT=32*1024*1024


def sofa_bytes(ident):
    if not re.fullmatch('[a-f0-9]{64}',ident):raise ValueError('Invalid HRTF identifier')
    with (ROOT/(ident+'.sofa')).open('rb') as stream:data=stream.read(LIMIT+1)
    if not 0<len(data)<=LIMIT or hashlib.sha256(data).hexdigest()!=ident:raise ValueError('Invalid HRTF file')
    return data


def profiles():
    result=[]
    if ROOT.is_dir():
        for file in sorted(ROOT.glob('*.json'))[:32]:
            try:
                if file.stat().st_size>2048:continue
                p=json.loads(file.read_text());ident=file.stem
                if re.fullmatch('[a-f0-9]{64}',ident) and isinstance(p.get('name'),str) and (ROOT/(ident+'.sofa')).is_file():
                    result.append((ident,p['name'][:64]))
            except (OSError,ValueError,TypeError):pass
    return result


def validate(library,data):
    from spatial_codec import Config,bind
    lib=C.CDLL(library);config=Config();handle=C.c_void_p()
    init=bind(lib,'openjoc_decoder_config_init_v1_7',C.c_int,C.POINTER(Config))
    create=bind(lib,'openjoc_decoder_create',C.c_int,C.POINTER(Config),C.POINTER(C.c_void_p))
    destroy=bind(lib,'openjoc_decoder_destroy',None,C.c_void_p)
    if init(C.byref(config))!=0:raise ValueError('SOFA_UNSUPPORTED')
    raw=C.create_string_buffer(data)
    config.render_mode=2;config.speaker_layout=b'7.1.4';config.virtual_layout=b'7.1.4'
    config.sofa=C.cast(raw,C.c_void_p);config.sofa_size=len(data);config.lfe=1
    try:
        if create(C.byref(config),C.byref(handle))!=0:raise ValueError('SOFA_UNSUPPORTED')
    finally:
        if handle:destroy(handle)


def import_sofa(source):
    from spatial_setup import configured,digest
    runtime=configured()
    if not runtime or digest(Path(runtime['decoder']))!=runtime['decoderSha256']:raise ValueError('SOFA_RUNTIME_REQUIRED')
    source=Path(source)
    if source.is_symlink() or not source.is_file() or not 0<source.stat().st_size<=LIMIT:raise ValueError('SOFA_SIZE_LIMIT')
    with source.open('rb') as stream:data=stream.read(LIMIT+1)
    if len(data)>LIMIT or not data.startswith((b'CDF\x01',b'\x89HDF\r\n\x1a\n')):raise ValueError('SOFA_UNSUPPORTED')
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    if len(profiles())>=32:raise ValueError('SOFA_LIBRARY_FULL')
    # Untrusted acoustic data is parsed by an isolated, bounded child, never by
    # the live decoder. Only the verified copy can later become a scene choice.
    with tempfile.NamedTemporaryFile(dir=ROOT,suffix='.candidate') as temporary:
        temporary.write(data);temporary.flush()
        try:
            checked=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--validate',runtime['decoder'],temporary.name],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15,
                env={**os.environ,'RAYON_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
        except subprocess.TimeoutExpired:raise ValueError('SOFA_UNSUPPORTED') from None
        if checked.returncode:raise ValueError('SOFA_UNSUPPORTED')
        ident=hashlib.sha256(data).hexdigest();target=ROOT/(ident+'.sofa')
        os.replace(temporary.name,target)
        # NamedTemporaryFile must not unlink the moved pathname on close.
        Path(temporary.name).touch(mode=0o600)
    name=''.join(c for c in source.stem if c.isprintable())[:64] or 'Personal HRTF'
    meta=ROOT/(ident+'.json');meta.write_text(json.dumps({'name':name},ensure_ascii=False));meta.chmod(0o600)
    return ident,name


if __name__=='__main__':
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_CPU,(10,10))
        resource.setrlimit(resource.RLIMIT_AS,(1536*1024*1024,1536*1024*1024))
        data=Path(sys.argv[3]).read_bytes()
        if len(data)>LIMIT:raise ValueError('SOFA_SIZE_LIMIT')
        validate(sys.argv[2],data)
    except Exception:raise SystemExit(1) from None
