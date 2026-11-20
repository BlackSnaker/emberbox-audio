#!/usr/bin/env python3
"""Package an exact Git revision, never the working tree or user profiles."""
import argparse
import gzip
import hashlib
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def git(*args):
    return subprocess.check_output(['git','-C',str(ROOT),*args])

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref',default='HEAD')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    commit=git('rev-parse',args.ref+'^{commit}').decode().strip()
    version=git('show',commit+':VERSION').decode().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-rc\.\d+)?',version):parser.error('Invalid release version')
    args.output.mkdir(parents=True,exist_ok=True)
    stem='emberbox-audio-'+version
    prefix=stem+'/'
    tar=git('archive','--format=tar','--prefix='+prefix,commit)
    files={stem+'-linux.tar.gz':gzip.compress(tar,mtime=0),
           stem+'-linux.zip':git('archive','--format=zip','--prefix='+prefix,commit)}
    for name,data in files.items():(args.output/name).write_bytes(data)
    (args.output/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in files.items()))
    (args.output/'BUILD-INFO.txt').write_text('Emberbox Audio\nVersion: '+version+'\nGit commit: '+commit+'\nPlatform: Linux\nPackage: source + dependency-aware installer; not a standalone binary\n')
    print('Built',version,'from',commit)
    for name,data in files.items():print(name,len(data),'bytes')

if __name__=='__main__':main()
