"""Build the optional Apple Lossless adapter from pinned, verified sources."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import tarfile
import urllib.request
from paths import CACHE_DIR,CONFIG_DIR

ROOT=CACHE_DIR/'apple-fairplay'
PROFILE=CONFIG_DIR/'apple-fairplay-profile'
REVISION='f2d66c3aa6a0cd78b41def391b2a08ed4af110e7'
ARCHIVE_SHA='73ddf6b50629542492ceb4473cd8fef1a7399fe9a97488c838fbe660b1fca6a3'
LOADERS={
    'drm/libhybris-core.so':'908b2b98134ef87ba68d083003a15caf5e05235ff4ab8df9c1e3a25bd2f770b6',
    'drm/hybris-linker/q.so':'b5725b3be908425d028d82b0f549fea5dba396cc3f1ad98bcd5ec9a86ab0b10c',
}


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(1048576):value.update(chunk)
    return value.hexdigest()


def download(url,path,sha,limit=32*1048576):
    if path.is_file() and digest(path)==sha:return
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temp=path.with_suffix(path.suffix+'.part')
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'Emberbox Audio optional Lossless setup'})
        with urllib.request.urlopen(request,timeout=30) as response,temp.open('wb') as out:
            total=0
            while chunk:=response.read(1048576):
                total+=len(chunk)
                if total>limit:raise RuntimeError('Lossless dependency exceeds its size limit.')
                out.write(chunk)
        if digest(temp)!=sha:raise RuntimeError('Lossless dependency checksum mismatch.')
        temp.replace(path)
    finally:temp.unlink(missing_ok=True)


def prepare(progress=lambda value:None):
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','amd64'):
        raise RuntimeError('The experimental Lossless adapter supports Linux x86_64.')
    for tool in ('gcc','g++','make','git'):
        if not shutil.which(tool):raise RuntimeError('Lossless setup needs '+tool+'. Run the installer with --apple-lossless.')
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    own=Path(__file__).resolve().parent/'fairplay_native'
    build_key=hashlib.sha256(REVISION.encode()+(own/'adam.patch').read_bytes()).hexdigest()[:16]
    source=ROOT/'source'/build_key
    archive=ROOT/'adam-source.tar.gz'
    progress('Verifying the optional Lossless sources')
    download('https://codeload.github.com/silentone12725/apple-music-linux/tar.gz/'+REVISION,archive,ARCHIVE_SHA,20*1048576)
    if not (source/'.patched').is_file():
        source.mkdir(parents=True,exist_ok=True,mode=0o700)
        with tarfile.open(archive,'r:gz') as package:
            for member in package.getmembers():
                parts=PurePosixPath(member.name).parts
                if len(parts)<2 or '..' in parts or not member.isfile():continue
                relative=PurePosixPath(*parts[1:])
                if parts[1]!='drm' and str(relative)!='LICENSE':continue
                if member.size>2*1048576:raise RuntimeError('Unexpected Lossless source file.')
                target=source/str(relative);target.parent.mkdir(parents=True,exist_ok=True)
                with package.extractfile(member) as stream:target.write_bytes(stream.read())
        result=subprocess.run(['git','apply',str(own/'adam.patch')],cwd=source,capture_output=True,timeout=10)
        if result.returncode:raise RuntimeError('Could not apply the pinned Lossless compatibility fixes.')
        (source/'.patched').touch()
    for name,sha in LOADERS.items():
        download('https://media.githubusercontent.com/media/silentone12725/apple-music-linux/'+REVISION+'/'+name,source/name,sha,2*1048576)
    lock=source/'drm/fairplay-libs.lock';origins=[];libraries=[]
    for line in lock.read_text().splitlines():
        fields=line.split()
        if len(fields)==2 and fields[0]=='source':origins.append(fields[1])
        elif len(fields)==2 and re.fullmatch('[a-f0-9]{64}',fields[0]) and re.fullmatch(r'lib[A-Za-z0-9_+.-]+\.so',fields[1]):
            libraries.append((fields[1],fields[0]))
    if len(libraries)!=22 or len(origins)!=2:raise RuntimeError('Unexpected Lossless dependency manifest.')
    progress('Downloading and verifying the optional native libraries')
    def fetch(item):
        name,sha=item
        for origin in origins:
            try:download(origin+'/'+name,ROOT/'lib64'/name,sha);return
            except (OSError,RuntimeError):pass
        raise RuntimeError('Could not fetch a verified Lossless dependency: '+name)
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(fetch,libraries))
    (ROOT/'linker').mkdir(exist_ok=True)
    shutil.copy2(source/'drm/hybris-linker/q.so',ROOT/'linker/q.so')
    library=ROOT/('libember-fairplay-'+build_key+'.so');checksum=library.with_suffix('.sha256')
    if not library.is_file() or not checksum.is_file() or checksum.read_text().strip()!=digest(library):
        progress('Building the isolated Lossless adapter')
        drm=source/'drm';blobs=drm/'embedded_blobs';blobs.mkdir(exist_ok=True)
        # .incbin avoids an optional xxd dependency and fails on missing input.
        asm=blobs/'libhybris-core.so.S'
        asm.write_text('.section .rodata\n.balign 8\n.global libhybris_core_so_data,libhybris_core_so_data_end,libhybris_core_so_size\nlibhybris_core_so_data:\n.incbin '+json.dumps(str(drm/'libhybris-core.so'),ensure_ascii=False)+'\nlibhybris_core_so_data_end:\n.balign 8\nlibhybris_core_so_size:\n.quad libhybris_core_so_data_end-libhybris_core_so_data\n.section .note.GNU-stack,"",@progbits\n')
        result=subprocess.run(['gcc','-c',str(asm),'-o',str(blobs/'libhybris-core.so.o')],capture_output=True,timeout=30)
        if result.returncode:raise RuntimeError('Could not embed the verified compatibility loader.')
        (blobs/'.blobs_built').touch()
        result=subprocess.run(['make','-C',str(drm),'-j2'],capture_output=True,timeout=180)
        if result.returncode:raise RuntimeError('Could not build Lossless support. Install C/C++, make, OpenSSL and libcurl development files.')
        temporary=library.with_suffix('.next.so');shutil.copy2(drm/'libdrm_client.so',temporary);temporary.replace(library)
        checksum.write_text(digest(library)+'\n')
    # Native Android libraries are fetched locally; none are redistributed.
    shutil.copy2(own/'LICENSE.adam',ROOT/'LICENSE.adam')
    shutil.copy2(lock,ROOT/'fairplay-libs.lock')
    PROFILE.mkdir(parents=True,exist_ok=True,mode=0o700);PROFILE.chmod(0o700)
    result={'schema':1,'revision':REVISION,'library':str(library),'librarySha256':digest(library),'profile':str(PROFILE)}
    target=ROOT/'runtime.json';temp=target.with_suffix('.next.json');temp.write_text(json.dumps(result));temp.chmod(0o600);temp.replace(target)
    progress('Lossless adapter ready; sign in from the player settings')
    return result


def configured(require_session=False):
    try:
        value=json.loads((ROOT/'runtime.json').read_text())
        if value.get('schema')!=1 or not Path(value['library']).is_file() or digest(Path(value['library']))!=value['librarySha256']:return None
        if require_session and not (Path(value['profile'])/'session-ready').is_file():return None
        return value
    except (OSError,ValueError,KeyError,TypeError):return None


if __name__=='__main__':
    try:prepare(lambda message:print('● '+message,flush=True))
    except Exception as error:raise SystemExit(str(error)) from None
