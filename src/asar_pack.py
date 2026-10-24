"""Package our JS application files in the standard ASAR/Pickle format.

No Node.js, package downloads, vendor code or browser profiles are involved.
The format follows electron/asar's disk.ts and pickle.ts.
"""
import hashlib
import json
from pathlib import Path
import struct


def pack(source,destination):
    source,destination = Path(source),Path(destination)
    files,data,offset = {},[],0
    for name in ('package.json','main.cjs','page.js','yandex.js','media_quality.cjs','flow.cjs','rhythm.cjs'):
        raw = (source/name).read_bytes()
        block_size = 4*1024*1024
        files[name] = {'size':len(raw),'offset':str(offset),'integrity':{
            'algorithm':'SHA256','hash':hashlib.sha256(raw).hexdigest(),'blockSize':block_size,
            'blocks':[hashlib.sha256(raw[n:n+block_size]).hexdigest() for n in range(0,len(raw),block_size)]}}
        data.append(raw)
        offset += len(raw)
    header = json.dumps({'files':files},separators=(',',':'),ensure_ascii=True).encode()
    payload = struct.pack('<I',len(header))+header+b'\0'*(-len(header)%4)
    pickle = struct.pack('<I',len(payload))+payload
    temporary = destination.with_suffix('.next.asar')
    temporary.write_bytes(struct.pack('<II',4,len(pickle))+pickle+b''.join(data))
    temporary.replace(destination)
