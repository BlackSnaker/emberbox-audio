"""Bounded, offline preparation for two licensed streams. Never runs on GTK."""
import math
import os
import select
import shutil
import subprocess
import time
import urllib.request
import numpy as np
from flow_beats import EnergyTap
from mashup_catalog import media_url,MAX_FILE

RATE=48000
MAX_SECONDS=600
MAX_PCM=RATE*MAX_SECONDS*8


def process(command,stop,timeout=180,**options):
    child=subprocess.Popen(command,stderr=subprocess.DEVNULL,**options)
    try:
        deadline=time.monotonic()+timeout
        while child.poll() is None:
            if stop.wait(.04):raise InterruptedError('cancelled')
            if time.monotonic()>deadline:raise TimeoutError('audio-preparation-timeout')
        if child.returncode:raise ValueError('audio-decoder-failed')
    finally:
        if child.poll() is None:
            child.terminate()
            try:child.wait(timeout=.5)
            except subprocess.TimeoutExpired:child.kill();child.wait()


def decode(item,stop,progress=lambda *_:None,*,start=0.,duration=None):
    """Fetch one selected CC BY asset to anonymous RAM, then decode locally.

    URLs are re-resolved by Catalog before this function. No cookies, browser
    profile, DRM components or microphone enter this path.
    """
    url=media_url(item.get('url'))
    if not url:raise ValueError('media-url-invalid')
    source=os.memfd_create('ember-mashup-input',os.MFD_CLOEXEC)
    output=os.memfd_create('ember-mashup-pcm',os.MFD_CLOEXEC)
    try:
        # ccMixter's public player sends its site origin for content requests.
        request=urllib.request.Request(url,headers={'User-Agent':'Emberbox-Audio/Mashups',
            'Referer':'https://ccmixter.org/'})
        class Redirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,request,fp,code,msg,headers,newurl):
                if not media_url(newurl):raise ValueError('media-redirect-invalid')
                return super().redirect_request(request,fp,code,msg,headers,newurl)
        opener=urllib.request.build_opener(Redirect)
        with opener.open(request,timeout=12) as response:
            if not media_url(response.url):raise ValueError('media-redirect-invalid')
            total=int(response.headers.get('Content-Length') or 0);received=0
            if total>MAX_FILE:raise ValueError('media-too-large')
            deadline=time.monotonic()+90
            while True:
                if stop.is_set():raise InterruptedError('cancelled')
                if time.monotonic()>deadline:raise TimeoutError('media-timeout')
                part=response.read(65536)
                if not part:break
                received+=len(part)
                if received>MAX_FILE:raise ValueError('media-too-large')
                os.write(source,part);progress(min(.95,received/total) if total else None)
            if not received or total and received!=total:raise ValueError('media-incomplete')
        os.lseek(source,0,0)
        ffmpeg=shutil.which('ffmpeg')
        if not ffmpeg:raise ValueError('ffmpeg-missing')
        # Read only the already validated in-memory object. Decoder protocols
        # cannot open network URLs, playlists or arbitrary local files.
        extension=url.rsplit('.',1)[-1].lower()
        demuxer={'mp3':'mp3','ogg':'ogg','flac':'flac','wav':'wav','m4a':'mov'}[extension]
        process([ffmpeg,'-nostdin','-v','error','-threads','1','-filter_threads','1',
            '-protocol_whitelist','file,pipe,fd','-f',demuxer,'-i',f'/proc/self/fd/{source}',
            '-ss',str(float(start)),'-t',str(duration if duration is not None else MAX_SECONDS+.05),
            '-vn','-ac','2','-ar',str(RATE),'-f','f32le','pipe:1'],
            stop,stdout=output,pass_fds=(source,))
        size=os.fstat(output).st_size
        if not 8<=size<=MAX_PCM or size%8:raise ValueError('audio-duration-limit')
        os.lseek(output,0,0)
        with os.fdopen(os.dup(output),'rb') as stream:raw=stream.read(MAX_PCM+8)
        pcm=np.frombuffer(raw,dtype='<f4').reshape(-1,2)
        if not np.isfinite(pcm).all():raise ValueError('audio-invalid')
        progress(1.);return pcm
    finally:os.close(source);os.close(output)


def analyse(pcm,known_bpm=0):
    # A short observation is enough for a constant-tempo proposal. Confidence
    # stays explicit; no invented grid is shown for unmetered/weak material.
    sample=pcm[:RATE*16];tap=EnergyTap()
    for start in range(0,len(sample),RATE//5):
        block=sample[start:start+RATE//5];tap.feed(block,(start+len(block))/RATE)
    beat=tap.result()
    if known_bpm:
        beat={**(beat or {}),'bpm':float(known_bpm),'confidence':(beat or {}).get('confidence',0),
              'phase':(beat or {}).get('phase',0),'provided':True}
    mono=sample[::4].mean(axis=1);rate=RATE/4
    chroma=np.zeros(12);window=np.hanning(4096)
    frequencies=np.fft.rfftfreq(4096,1/rate)
    usable=(frequencies>75)&(frequencies<3500)
    notes=np.rint(69+12*np.log2(frequencies[usable]/440)).astype(int)%12
    for start in range(0,max(0,len(mono)-4096),2048):
        energy=np.abs(np.fft.rfft(mono[start:start+4096]*window))[usable]**.7
        chroma+=np.bincount(notes,weights=energy,minlength=12)
    norm=float(np.linalg.norm(chroma));key=None
    if norm>1e-8:
        profile=chroma/norm;rank=[]
        for mode,template in [('major',[6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88]),
                              ('minor',[6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])]:
            centered=profile-profile.mean()
            for root in range(12):
                target=np.roll(template,root);target=target-np.mean(target)
                score=float(np.dot(centered,target)/(np.linalg.norm(centered)*np.linalg.norm(target)+1e-12))
                rank.append((score,root,mode))
        rank.sort(reverse=True);score,root,mode=rank[0]
        key={'root':root,'mode':mode,'confidence':max(0.,score),'margin':max(0.,score-rank[1][0])}
    return {'beat':beat,'key':key}


def plan(first,second,settings):
    a,b=first.get('beat') or {},second.get('beat') or {}
    tempo=float(settings.get('tempo') or 0)
    if not tempo and settings.get('auto') and a.get('bpm') and b.get('bpm'):tempo=b['bpm']
    rates=[]
    for source in (a,b):
        bpm=source.get('bpm') or 0
        if tempo and bpm:
            rate=min((tempo/(bpm*f) for f in (.5,1,2)),key=lambda r:abs(r-1))
            # Dramatic stretching is not quietly labelled a good automatic mix.
            if not .8<=rate<=1.25:raise ValueError('tempo-too-far')
        else:rate=1.
        rates.append(rate)
    shift=int(settings.get('shift') or 0)
    ka,kb=first.get('key') or {},second.get('key') or {}
    if settings.get('auto') and not shift and min(ka.get('confidence',0),kb.get('confidence',0))>.65 and min(ka.get('margin',0),kb.get('margin',0))>.035:
        signature_a=(ka['root']+(3 if ka.get('mode')=='minor' else 0))%12
        signature_b=(kb['root']+(3 if kb.get('mode')=='minor' else 0))%12
        candidate=(signature_a-signature_b+6)%12-6
        if abs(candidate)<=3:shift=candidate
    offset=float(settings.get('offset') or 0)
    if settings.get('auto') and not offset and min(a.get('confidence',0),b.get('confidence',0))>=.72:
        offset=a['phase']/rates[0]-b['phase']/rates[1]
    return {'tempo':tempo,'rates':rates,'shift':shift,'offset':offset,
        'beatMatched':bool(tempo and a.get('bpm') and b.get('bpm')),'analyses':[first,second]}


def transform(pcm,rate,semitones,stop):
    if abs(rate-1)<.0001 and semitones==0:return pcm
    executable=shutil.which('ffmpeg')
    if not executable:raise ValueError('ffmpeg-missing')
    filters=subprocess.run([executable,'-hide_banner','-filters'],capture_output=True,text=True,timeout=5)
    if ' rubberband ' not in filters.stdout:raise ValueError('rubberband-missing')
    source=os.memfd_create('ember-mashup-stretch',os.MFD_CLOEXEC)
    output=os.memfd_create('ember-mashup-stretched',os.MFD_CLOEXEC)
    try:
        view=memoryview(np.ascontiguousarray(pcm,dtype='<f4')).cast('B')
        while view:
            if stop.is_set():raise InterruptedError('cancelled')
            written=os.write(source,view[:262144]);view=view[written:]
        os.lseek(source,0,0)
        process([executable,'-nostdin','-v','error','-threads','1','-filter_threads','1',
            '-f','f32le','-ar',str(RATE),'-ac','2','-i',f'/proc/self/fd/{source}',
            '-af',f'rubberband=tempo={rate:.8f}:pitch={2**(semitones/12):.8f}:pitchq=quality',
            '-t',str(MAX_SECONDS),'-f','f32le','pipe:1'],stop,stdout=output,pass_fds=(source,))
        size=os.fstat(output).st_size
        if not 8<=size<=MAX_PCM or size%8:raise ValueError('audio-duration-limit')
        os.lseek(output,0,0)
        with os.fdopen(os.dup(output),'rb') as stream:return np.frombuffer(stream.read(),dtype='<f4').reshape(-1,2)
    finally:os.close(source);os.close(output)


def separate(pcm,role,provided,stop,progress=lambda *_:None,separator=None):
    if role=='song' or role==provided:return pcm
    if separator is None:
        from karaoke_neural import NeuralSeparator
        separator=NeuralSeparator()
    from karaoke_neural import WINDOW_SAMPLES
    width=WINDOW_SAMPLES;hop=width//2
    result=np.zeros_like(pcm);weight=np.zeros(len(pcm),np.float32)
    window=np.hanning(width).astype(np.float32)
    for start in range(-hop,len(pcm),hop):
        if stop.is_set():raise InterruptedError('cancelled')
        # Reflect only a small context at the edges, not another whole song.
        indices=np.arange(start,start+width)
        if len(pcm)>1:
            indices=np.abs(indices)%(2*len(pcm)-2);indices=np.minimum(indices,2*len(pcm)-2-indices)
        else:indices[:]=0
        voice=separator.vocals(pcm[indices])
        left=max(0,start);right=min(len(pcm),start+width);part=slice(left-start,right-start)
        result[left:right]+=voice[part]*window[part,None];weight[left:right]+=window[part]
        progress(min(1.,right/len(pcm)))
    result/=np.maximum(weight[:,None],1e-8)
    if role=='instrumental':np.subtract(pcm,result,out=result)
    return result


def waveform(pcm,bins=256):
    edges=np.linspace(0,len(pcm),bins+1,dtype=int)
    return [round(float(np.max(np.abs(pcm[a:b]))) if b>a else 0.,4) for a,b in zip(edges,edges[1:])]


def render(first,second,settings,proposal):
    offset=round(proposal['offset']*RATE)
    a_start=max(0,-offset);b_start=max(0,offset)
    length=max(a_start+len(first),b_start+len(second)) if settings['whole'] else round(settings['length']*RATE)
    length=min(length,RATE*MAX_SECONDS)
    output=np.zeros((length,2),np.float32)
    # Both parts retain their natural extent. A shorter source fades out;
    # the longer source can finish without an invented repeated vocal phrase.
    for index,(pcm,start) in enumerate(((first,a_start),(second,b_start))):
        count=min(len(pcm),max(0,length-start))
        if not count:continue
        gain=float(settings['tracks'][index]['gain']);fade=min(RATE//25,count//2)
        for at in range(0,count,RATE):
            end=min(count,at+RATE);part=pcm[at:end]*gain
            positions=np.arange(at,end)
            envelope=np.minimum(1.,np.minimum(positions/max(1,fade),(count-1-positions)/max(1,fade)))
            part*=np.maximum(envelope,0)[:,None]
            output[start+at:start+end]+=part
    peak=float(np.max(np.abs(output))) if len(output) else 0.
    attenuation=min(1.,.98/max(peak,1e-12));output*=attenuation
    if not np.isfinite(output).all():raise ValueError('audio-invalid')
    return output,attenuation
