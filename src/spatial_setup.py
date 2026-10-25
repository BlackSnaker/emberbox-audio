"""Prepare the optional native Apple audio path, without blocking the GTK thread."""
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from paths import CACHE_DIR

ROOT=CACHE_DIR/'apple-spatial'
VERSION='0.20.1'
ARCHIVE=f'openjoc-{VERSION}-x86_64-unknown-linux-gnu.tar.gz'
SHA256='a031c473f3036700f66c81337ed73db8734a86b5086989e219e6bd0e1babe72c'


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(1024*1024):value.update(chunk)
    return value.hexdigest()


def prepare(progress=lambda value:None):
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','amd64'):
        raise RuntimeError('The experimental spatial runtime currently supports Linux x86_64.')
    libc,libc_version=platform.libc_ver()
    if libc=='glibc' and tuple(int(p) for p in libc_version.split('.')[:2])<(2,34):
        raise RuntimeError('Apple spatial audio needs glibc 2.34 or newer.')
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    compiler=shutil.which('c++') or shutil.which('g++') or shutil.which('clang++')
    if not compiler:raise RuntimeError('Install a C++ compiler for Apple spatial audio.')
    source=Path(__file__).resolve().parent/'spatial_native'
    version=subprocess.check_output([compiler,'--version'],text=True,timeout=5)
    key=hashlib.sha256(version.encode()+b''.join(p.read_bytes() for p in sorted(source.iterdir()) if p.is_file())).hexdigest()[:16]
    host=ROOT/f'cdm-host-{key}.so'
    if not host.is_file():
        progress('Building the native audio adapter')
        temporary=host.with_suffix('.next.so')
        result=subprocess.run([compiler,'-std=c++17','-O2','-fPIC','-shared',str(source/'host.cc'),'-ldl','-o',str(temporary)],capture_output=True,text=True,timeout=90)
        if result.returncode:
            temporary.unlink(missing_ok=True)
            raise RuntimeError('Could not build the native audio adapter with the installed C++ compiler.')
        temporary.replace(host)
    decoder=ROOT/f'libopenjoc-{VERSION}.so'
    notice=ROOT/f'OpenJOC-{VERSION}-LICENSE'
    if not decoder.is_file() or not notice.is_file():
        archive=ROOT/ARCHIVE
        if not archive.is_file() or digest(archive)!=SHA256:
            progress('Downloading the spatial decoder')
            temporary=archive.with_suffix('.part')
            request=urllib.request.Request(f'https://github.com/chyinan/OpenJOC/releases/download/v{VERSION}/{ARCHIVE}',headers={'User-Agent':'Emberbox Audio spatial setup'})
            try:
                with urllib.request.urlopen(request,timeout=30) as response,temporary.open('wb') as out:
                    total=0;reported=0
                    while chunk:=response.read(1024*1024):
                        total+=len(chunk)
                        if total>110*1024*1024:raise RuntimeError('Spatial decoder archive exceeds its size limit.')
                        out.write(chunk)
                        if total-reported>=8*1024*1024:
                            reported=total;progress(f'Downloading the spatial decoder: {total//1048576} MB')
                if digest(temporary)!=SHA256:raise RuntimeError('Spatial decoder checksum mismatch.')
                temporary.replace(archive)
            finally:temporary.unlink(missing_ok=True)
        progress('Verifying the spatial decoder')
        name=f'openjoc-{VERSION}-x86_64-unknown-linux-gnu/lib/libopenjoc_capi.so'
        with tarfile.open(archive,'r:gz') as package:
            member=package.getmember(name)
            if not member.isfile() or not 0<member.size<64*1024*1024:raise RuntimeError('Unexpected spatial library.')
            temporary=decoder.with_suffix('.next.so')
            with package.extractfile(member) as stream,temporary.open('wb') as out:shutil.copyfileobj(stream,out)
            temporary.replace(decoder)
            license_member=package.getmember(f'openjoc-{VERSION}-x86_64-unknown-linux-gnu/LICENSE')
            if not license_member.isfile() or license_member.size>65536:raise RuntimeError('Unexpected decoder license.')
            with package.extractfile(license_member) as stream:notice.write_bytes(stream.read())
    checked=subprocess.run([sys.executable,'-I','-c',
        'import ctypes,sys;lib=ctypes.CDLL(sys.argv[1]);lib.openjoc_get_abi_version.restype=ctypes.c_uint32;assert lib.openjoc_get_abi_version()==0x10007;ctypes.CDLL(sys.argv[2])',str(decoder),str(host)],capture_output=True,timeout=10)
    if checked.returncode:raise RuntimeError('The spatial decoder needs Linux x86_64 with glibc 2.34 or newer.')
    result={'schema':1,'host':str(host),'hostSha256':digest(host),'decoder':str(decoder),
            'decoderSha256':digest(decoder),'version':VERSION}
    target=ROOT/'runtime.json';temporary=target.with_suffix('.next.json')
    temporary.write_text(json.dumps(result));temporary.chmod(0o600);temporary.replace(target)
    progress('Spatial audio runtime ready')
    return result


def configured():
    try:
        value=json.loads((ROOT/'runtime.json').read_text())
        return value if value.get('schema')==1 and all(Path(value.get(k,'')).is_file() for k in ('host','decoder')) else None
    except (OSError,ValueError,TypeError):return None


if __name__=='__main__':
    try:prepare(lambda message:print('● '+message,flush=True))
    except Exception as error:raise SystemExit(str(error)) from None
