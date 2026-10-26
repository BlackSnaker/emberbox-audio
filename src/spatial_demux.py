"""Bounded CMAF audio sample parsing. Encryption remains with the installed CDM."""
import copy
from spatial_mp4 import boxes


def uint(data,p,n,end):
    if n not in (1,2,4,8) or p<0 or p+n>end:raise ValueError('Truncated CMAF field')
    return int.from_bytes(data[p:p+n],'big')


def encryption(data,p,end):
    # tenc full box: version/flags, reserved, pattern, protected, IV size, KID.
    if end-p<24:raise ValueError('Truncated tenc')
    version=data[p];pattern=data[p+5] if version else 0
    protected=data[p+6];iv_size=data[p+7];kid=bytes(data[p+8:p+24]);at=p+24
    if protected!=1 or iv_size not in (0,8,16):raise ValueError('Unsupported audio encryption')
    iv=None
    if not iv_size:
        length=uint(data,at,1,end);at+=1
        if length not in (8,16) or at+length>end:raise ValueError('Invalid constant IV')
        iv=bytes(data[at:at+length]).ljust(16,b'\0')
    return {'iv_size':iv_size,'iv':iv,'kid':kid,'crypt':pattern>>4,'skip':pattern&15,'scheme':2}


def audio_specific_config(data,start,end,depth=0):
    if depth>3:raise ValueError('AAC descriptor nesting limit')
    while start<end:
        tag=uint(data,start,1,end);start+=1;size=0
        for _ in range(4):
            value=uint(data,start,1,end);start+=1;size=(size<<7)|(value&127)
            if not value&128:break
        else:raise ValueError('AAC descriptor length limit')
        limit=start+size
        if limit>end:raise ValueError('Truncated AAC descriptor')
        nested=None
        if tag==5:return bytes(data[start:limit])
        if tag==3:
            flags=uint(data,start+2,1,limit);nested=start+3
            if flags&128:nested+=2
            if flags&64:nested+=1+uint(data,nested,1,limit)
            if flags&32:nested+=2
        elif tag==4:nested=start+13
        if nested is not None:
            if nested>limit:raise ValueError('Truncated AAC descriptor')
            result=audio_specific_config(data,nested,limit,depth+1)
            if result:return result
        start=limit
    return None


def initialization(data,end):
    trex={};descriptions=[];timescale=None
    def entry(kind,p,q):
        codec={b'ec-3':'eac3',b'mp4a':'aac',b'alac':'alac'}.get(kind);scheme=None;configs=[];asc=None;cookie=None
        if kind not in (b'enca',b'ec-3',b'mp4a',b'alac'):return None
        version=uint(data,p+8,2,q)
        if version not in (0,1,2):return None
        def walk(start,limit,depth=0):
            nonlocal codec,scheme,asc,cookie
            if depth>6:raise ValueError('CMAF nesting limit')
            for kind,_,p,q in boxes(data,start,limit):
                if kind in (b'sinf',b'schi',b'wave'):walk(p,q,depth+1)
                elif kind==b'frma':codec={b'ec-3':'eac3',b'mp4a':'aac',b'alac':'alac'}.get(bytes(data[p:p+4]))
                elif kind==b'schm':scheme=bytes(data[p+4:p+8])
                elif kind==b'esds':asc=audio_specific_config(data,p+4,q)
                elif kind==b'alac':
                    if q-p!=28:raise ValueError('Invalid ALAC configuration')
                    cookie=bytes(data[p-8:q])
                elif kind==b'tenc':configs.append(encryption(data,p,q))
        walk(p+{0:28,1:44,2:64}[version],q)
        if not codec or len(configs)!=1 or scheme not in (b'cbcs',b'cenc'):return None
        return {**configs[0],'codec':codec,'asc':asc,'cookie':cookie,'scheme':2 if scheme==b'cbcs' else 1}
    def walk(start,limit,depth=0):
        nonlocal timescale
        if depth>12:raise ValueError('CMAF nesting limit')
        for kind,_,p,q in boxes(data,start,limit):
            if kind in (b'moov',b'trak',b'mdia',b'minf',b'stbl',b'mvex'):walk(p,q,depth+1)
            elif kind==b'mdhd':
                version=uint(data,p,1,q)
                if version not in (0,1):raise ValueError('Unsupported CMAF timescale')
                timescale=uint(data,p+(12 if version==0 else 20),4,q)
                if not timescale:raise ValueError('Invalid CMAF timescale')
            elif kind==b'stsd':
                if descriptions:raise ValueError('Multiple audio tracks unsupported')
                count=uint(data,p+4,4,q)
                if not 0<count<=16:raise ValueError('CMAF description limit')
                descriptions.extend(entry(k,a,b) for k,_,a,b in boxes(data,p+8,q))
                if len(descriptions)!=count:raise ValueError('CMAF description count')
            elif kind==b'trex':
                track=uint(data,p+4,4,q);trex[track]={'description':uint(data,p+8,4,q),'duration':uint(data,p+12,4,q),'size':uint(data,p+16,4,q)}
    walk(0,end)
    if not any(descriptions):raise ValueError('Unsupported CMAF audio initialization')
    for description in descriptions:
        if description is not None:description['timescale']=timescale
    return trex,descriptions


def sample_crypto(data,p,end,config,subsamples):
    iv=config['iv']
    if config['iv_size']:
        n=config['iv_size']
        if p+n>end:raise ValueError('Truncated sample IV')
        iv=bytes(data[p:p+n]).ljust(16,b'\0');p+=n
    pairs=[]
    if subsamples:
        count=uint(data,p,2,end);p+=2
        if count>1024:raise ValueError('Too many subsamples')
        for _ in range(count):
            pairs.append((uint(data,p,2,end),uint(data,p+2,4,end)));p+=6
    return {**config,'iv':iv,'pairs':pairs},p


def samples(data,init_size,original_offset):
    if not 0<init_size<len(data)<=18*1024*1024:raise ValueError('CMAF bounds')
    defaults,descriptions=initialization(data,init_size);produced=0
    for kind,moof,p,end in boxes(data,init_size,len(data)):
        if kind!=b'moof':continue
        original_moof=original_offset+moof-init_size
        for kind,_,p2,end2 in boxes(data,p,end):
            if kind!=b'traf':continue
            children=list(boxes(data,p2,end2));headers=[b for b in children if b[0]==b'tfhd']
            if len(headers)!=1:raise ValueError('Unsupported CMAF track fragment')
            _,_,h,hend=headers[0];flags=uint(data,h,4,hend)&0xffffff;track=uint(data,h+4,4,hend);at=h+8
            base=original_moof
            if flags&1:base=uint(data,at,8,hend);at+=8
            default=copy.copy(defaults.get(track,{}))
            if flags&2:default['description']=uint(data,at,4,hend);at+=4
            description=default.get('description',1)
            if not 0<description<=len(descriptions) or descriptions[description-1] is None:raise ValueError('Unsupported selected CMAF description')
            default_crypto=descriptions[description-1]
            if flags&8:default['duration']=uint(data,at,4,hend);at+=4
            if flags&16:default['size']=uint(data,at,4,hend);at+=4
            sizes=[];positions=[];durations=[];next_pos=None
            for kind,_,r,rend in children:
                if kind!=b'trun':continue
                f=uint(data,r,4,rend)&0xffffff;count=uint(data,r+4,4,rend);at=r+8
                if count>2048 or len(sizes)+count>2048:raise ValueError('CMAF sample limit')
                if f&1:
                    offset=uint(data,at,4,rend);offset=offset-(1<<32) if offset&(1<<31) else offset;at+=4
                    next_pos=moof+(base-original_moof)+offset
                if f&4:at+=4
                if next_pos is None:raise ValueError('Missing CMAF data offset')
                for _ in range(count):
                    duration=uint(data,at,4,rend) if f&256 else default.get('duration',0)
                    if f&256:at+=4
                    size=uint(data,at,4,rend) if f&512 else default.get('size',0)
                    if f&512:at+=4
                    if f&1024:at+=4
                    if f&2048:at+=4
                    if at>rend or not 0<size<=1048576 or not init_size<=next_pos<=len(data)-size:raise ValueError('Invalid CMAF sample range')
                    sizes.append(size);durations.append(duration);positions.append(next_pos);next_pos+=size
            if not sizes:continue
            config=copy.copy(default_crypto)
            # Key rotation via HLS uses the declared playlist KID when tenc KID
            # is zero. Unsupported seig overrides must not silently use defaults.
            if any(k==b'sgpd' and bytes(data[r+4:r+8])==b'seig' for k,_,r,_ in children):raise ValueError('Unsupported seig override')
            crypto=[];senc=next((b for b in children if b[0]==b'senc'),None)
            if senc:
                _,_,at,q=senc;f=uint(data,at,4,q)&0xffffff
                if f&1:raise ValueError('Unsupported senc override')
                count=uint(data,at+4,4,q);at+=8
                if count!=len(sizes):raise ValueError('Mismatched senc count')
                for _ in sizes:
                    value,at=sample_crypto(data,at,q,config,bool(f&2));crypto.append(value)
            else:
                saiz=next((b for b in children if b[0]==b'saiz'),None);saio=next((b for b in children if b[0]==b'saio'),None)
                if saiz and saio:
                    _,_,at,q=saiz;f=uint(data,at,4,q)&0xffffff;at+=4+(8 if f&1 else 0)
                    fixed=uint(data,at,1,q);count=uint(data,at+1,4,q);at+=5
                    if count!=len(sizes):raise ValueError('Mismatched auxiliary count')
                    lengths=[fixed]*count if fixed else [uint(data,at+i,1,q) for i in range(count)]
                    _,_,at,q=saio;version=data[at];f=uint(data,at,4,q)&0xffffff;at+=4+(8 if f&1 else 0)
                    count=uint(data,at,4,q);at+=4
                    if count!=1 or version not in (0,1):raise ValueError('Unsupported auxiliary offsets')
                    offset=uint(data,at,8 if version else 4,q);at=moof+(base-original_moof)+offset
                    for length in lengths:
                        end_info=at+length
                        if end_info>len(data):raise ValueError('Truncated auxiliary info')
                        value,used=sample_crypto(data,at,end_info,config,length>config['iv_size'])
                        if used!=end_info:raise ValueError('Invalid auxiliary length')
                        crypto.append(value);at=end_info
                elif config['iv_size']==0:
                    crypto=[{**config,'pairs':[]} for _ in sizes]
                else:raise ValueError('Missing sample encryption info')
            for at,size,duration,value in zip(positions,sizes,durations,crypto):
                if value['pairs'] and sum(a+b for a,b in value['pairs'])!=size:raise ValueError('Invalid encrypted subsample sizes')
                produced+=1
                if produced>2048:raise ValueError('CMAF sample limit')
                yield bytes(data[at:at+size]),{**value,'duration':duration}
    if not produced:raise ValueError('No CMAF audio samples')
