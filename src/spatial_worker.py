#!/usr/bin/env python3
"""Isolated Apple spatial audio worker. Opaque DRM messages, never key exports."""
import base64
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import resource
import sys
import threading
import time
import uuid
from spatial_codec import Cdm,Joc,key_identifier
from spatial_demux import samples
from spatial_aac import Aac,PcmResampler,configuration
from spatial_alac import Alac,configuration as alac_configuration
from spatial_fairplay import FairPlay
from spatial_seek import Seeks,SeekCancelled,PcmWriter

resource.setrlimit(resource.RLIMIT_CORE,(0,0))
# PR_SET_DUMPABLE also prevents system crash handlers from retaining audio.
import ctypes
if ctypes.CDLL(None).prctl(4,0,0,0,0)!=0:raise RuntimeError('SPATIAL_DUMP_PROTECTION')
if ctypes.CDLL(None).prctl(1,15,0,0,0)!=0:raise RuntimeError('SPATIAL_PARENT_PROTECTION')
if os.getppid()==1:os._exit(1)

lock=threading.Lock();pending={};stopping=threading.Event();bootstrap=queue.Queue(1)
seeks=Seeks()
control=os.fdopen(os.dup(1),'w',buffering=1)

def emit(value):
    with lock:control.write(json.dumps(value,separators=(',',':'))+'\n')

def listen():
    try:
        while not stopping.is_set():
            raw=sys.stdin.buffer.readline(4*1024*1024+1)
            if not raw or len(raw)>4*1024*1024:break
            value=json.loads(raw)
            if value.get('type')=='start':
                seeks.submit(value.get('position',0),value['generation']);bootstrap.put_nowait(value)
            elif value.get('type')=='seek':
                seeks.submit(value['position'],value['generation'])
                emit({'type':'seek-state','generation':value['generation'],'stage':'requested'})
            elif value.get('type')=='response':
                target=pending.get(value.get('id'))
                if target:target.put_nowait(value)
            elif value.get('type')=='stop':break
    except Exception:pass
    finally:stopping.set();seeks.close()

def request(action,cancelled=None,**params):
    ident=uuid.uuid4().hex;reply=queue.Queue(1);pending[ident]=reply
    try:
        emit({'type':'request','id':ident,'action':action,**params})
        until=time.monotonic()+16
        while not stopping.is_set() and time.monotonic()<until:
            if cancelled is not None and cancelled.is_set():raise SeekCancelled()
            try:
                response=reply.get(timeout=.1)
                if response.get('error'):raise RuntimeError(response['error'])
                return response.get('result') or {}
            except queue.Empty:pass
        raise RuntimeError('SPATIAL_NETWORK_TIMEOUT')
    finally:pending.pop(ident,None)

def decode64(value,max_size):
    if not isinstance(value,str) or len(value)>max_size*4//3+8:raise ValueError('Invalid spatial message')
    result=base64.b64decode(value,validate=True)
    if len(result)>max_size:raise ValueError('Spatial message too large')
    return result

def decode_pass(args,prepared,runtime,rate,cdm,licensed,license_key,writer,origin,generation,cancelled):
    emit({'type':'seek-state','generation':generation,'stage':'decoding'})
    segments=prepared['segments'];index=next((i for i,s in enumerate(segments) if s['start']+s['duration']>origin),len(segments)-1)
    skip=round(max(0.,origin-segments[index]['start'])*rate)
    decoded=0;emitted=0;expected=0.;verified=False;rendered_format=None;joc=resampler=None
    fairplay=prepared.get('drm')=='fairplay'
    def output(data,samples):
        nonlocal skip,decoded,emitted,verified
        if cancelled.is_set():raise SeekCancelled()
        decoded+=samples
        remove=min(skip,samples);skip-=remove;data=data[remove*8:]
        if not data:return
        if not verified:
            verified=True;emit({'type':'quality','generation':generation,'audioQuality':rendered_format})
        writer.write(data,generation,cancelled);emitted+=len(data)//8
    try:
        for number in range(index,len(segments)):
            if cancelled.is_set():raise SeekCancelled()
            segment=segments[number];key=segment['keyIndex'];license_key(key)
            encrypted=bytearray();total=1
            while len(encrypted)<total:
                part=request('segment',cancelled=cancelled,index=number,offset=len(encrypted));total=part['total']
                if not isinstance(total,int) or not 0<total<=18*1024*1024:raise RuntimeError('SPATIAL_SOURCE_LIMIT')
                chunk=decode64(part['data'],393216)
                if not chunk or len(encrypted)+len(chunk)>total:raise RuntimeError('SPATIAL_SOURCE_INVALID')
                encrypted.extend(chunk)
            for packet,crypto in samples(encrypted,part['initBytes'],part['originalOffset']):
                if cancelled.is_set():raise SeekCancelled()
                # E-AC-3 access units are independently encrypted. Keep half a
                # second of JOC/HRTF warm-up, without rendering many seconds of
                # discarded audio before a deep seek inside a long HLS segment.
                # Never alter the selected asset, decoder or audible packets.
                duration=crypto.get('duration',0)
                if not args.get('fullPreroll') and number==index and crypto.get('codec')=='eac3' and crypto.get('timescale')==48000 and 0<duration<=6144:
                    frames=round(duration*rate/48000)
                    if skip-frames>=rate*.5:
                        skip-=frames;decoded+=frames;continue
                if joc is None:
                    if crypto.get('codec')=='alac' and prepared.get('codec')=='alac' and fairplay:
                        _,depth,source_rate=alac_configuration(crypto.get('cookie') or b'')
                        rendered_format={'codec':'alac','evidence':'decoder','sampleRate':source_rate,'bitDepth':depth,'channels':2,'outputSampleRate':rate}
                        joc=Alac(crypto['cookie'],output,cancelled,output_rate=rate)
                    elif crypto.get('codec')=='aac' and prepared.get('codec')=='aac':
                        source_rate=configuration(crypto.get('asc') or b'')[1]
                        rendered_format={'codec':'aac','evidence':'decoder','sampleRate':source_rate,'channels':2,'outputSampleRate':rate}
                        joc=Aac(crypto['asc'],output,cancelled,output_rate=rate)
                    elif crypto.get('codec')=='eac3':
                        rendered_format={'codec':'eac3','variant':'dolby-atmos','evidence':'decoder','sampleRate':48000,'channels':2,'renderer':'openjoc-binaural','outputSampleRate':rate}
                        if rate!=48000:resampler=PcmResampler(48000,rate,output,cancelled)
                        joc=Joc(runtime['decoder'],resampler.write if resampler else output)
                    else:raise RuntimeError('SPATIAL_CODEC_MISMATCH')
                    seeks.attach(joc,cancelled)
                    if resampler:seeks.attach(resampler,cancelled)
                    emit({'type':'seek-state','generation':generation,'stage':'codec-ready'})
                if isinstance(joc,Alac):joc.packet_duration=crypto['duration']
                cdm.decode_sample(packet,crypto,licensed[key],joc.feed)
            expected+=segment['duration']
            # The resampler delivers PCM on another thread. Its buffered tail
            # is not missing audio; validate it after finish() has drained it.
            if not isinstance(joc,Aac) and resampler is None and decoded<expected*rate-rate*.15:raise RuntimeError('SPATIAL_TRUNCATED_AUDIO')
        if joc is None:raise RuntimeError('SPATIAL_EMPTY_FRAGMENT')
        joc.finish()
        if resampler:
            resampler.finish()
            if decoded<expected*rate-rate*.15:raise RuntimeError('SPATIAL_TRUNCATED_AUDIO')
        if cancelled.is_set():raise SeekCancelled()
        emit({'type':'decoded-end','generation':generation,'frames':emitted})
    finally:
        if joc:joc.close()
        if resampler:resampler.close()


def main():
    threading.Thread(target=listen,daemon=True).start()
    args=bootstrap.get(timeout=10);runtime=args['runtime'];prepared=args['prepared']
    for key in ('host','decoder'):
        value=hashlib.sha256()
        with Path(runtime[key]).open('rb') as stream:
            while chunk:=stream.read(1024*1024):value.update(chunk)
        if value.hexdigest()!=runtime[key+'Sha256']:raise RuntimeError('SPATIAL_RUNTIME_CHANGED')
    rate=int(args.get('outputRate',48000))
    if rate not in (48000,192000):raise RuntimeError('SPATIAL_PCM_FORMAT')
    cdm=None
    try:
        fairplay=prepared.get('drm')=='fairplay'
        if fairplay:
            # Native vendor output must never enter the control pipe or journal.
            with open(os.devnull,'wb') as quiet:
                os.dup2(quiet.fileno(),1);os.dup2(quiet.fileno(),2)
            cdm=FairPlay(runtime['fairplay'])
        else:
            cdm=Cdm(runtime['host'],args['cdm']);cdm.call('certificate',decode64(prepared['certificate'],131072))
        writer=PcmWriter(3,stopping)
        licensed={}
        def license_key(key):
            if key in licensed:return
            if fairplay:
                licensed[key]=cdm.license(prepared['metadata']['catalogId'],prepared['licences'][key]['uri']);return
            init=decode64(prepared['licences'][key]['pssh'],131072);kid=key_identifier(init)
            challenge=cdm.challenge(init)
            response=request('license',index=key,challenge=base64.b64encode(challenge).decode())
            cdm.call('update',decode64(response['license'],131072))
            until=time.monotonic()+3
            while not cdm.usable(cdm.handle) and time.monotonic()<until:time.sleep(.01)
            if not cdm.usable(cdm.handle):raise RuntimeError('SPATIAL_KEY_UNUSABLE')
            licensed[key]=kid
        if fairplay:
            # Confirm the full song before starting, including its rotated key.
            for key in range(len(prepared['licences'])):license_key(key)
        # Keep the same source context, CDM and licensed handles across seeks.
        # Only codec state and bounded PCM queues are replaced. EOF stays warm.
        while value:=seeks.next():
            origin,generation,cancelled=value
            try:decode_pass(args,prepared,runtime,rate,cdm,licensed,license_key,writer,origin,generation,cancelled)
            except Exception:
                if not cancelled.is_set():raise
    finally:
        seeks.close()
        try:os.close(3)
        except OSError:pass
        if cdm:cdm.close()

if __name__=='__main__':
    try:main()
    except Exception as error:
        code=str(error)
        emit({'type':'error','exception':type(error).__name__,'hint':code if isinstance(error,ValueError) and re.fullmatch(r'[A-Za-z -]{1,90}',code) else '', 'diagnostics':getattr(error,'diagnostics',None),'code':code if code.startswith('SPATIAL_') or code in ('DEVICE_LIMIT','SUBSCRIPTION_REQUIRED','SIGN_IN_REQUIRED') else 'SPATIAL_PLAYBACK_FAILED'})
        raise SystemExit(1)
