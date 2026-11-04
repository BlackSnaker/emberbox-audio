"""On-demand translation of public editorial prose, isolated from playback.

Google Translate's public web endpoint is not the authenticated Cloud API and
has no availability contract. Keep the original, report failures and never send
account state. Only a deliberate reader action starts a request.
"""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import urllib.parse
import urllib.request

from paths import CACHE_DIR

ENDPOINT = 'https://translate.googleapis.com/translate_a/single'
MAX_TEXT = 14_000
MAX_REPLY = 512_000
CHUNK = 3_800
TTL = 30 * 86400
PROVIDER = 'google-web-ru-v1'
CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


class TranslationError(Exception):
    """The complete translation could not be obtained; retain the original."""


def clean(value):
    if not isinstance(value, str):raise TranslationError('Invalid text')
    value=CONTROL.sub('', value.replace('\r\n','\n').replace('\r','\n')).strip()
    if not value or len(value)>MAX_TEXT:raise TranslationError('Invalid text length')
    return value


def identity(value):
    return hashlib.sha256((PROVIDER+'\0'+value).encode('utf-8')).hexdigest()


def is_russian(value):
    """Conservative shortcut for source-supplied Russian, including Latin names."""
    letters=re.findall(r'[^\W\d_]',value, re.UNICODE)
    if re.search('[іїєґІЇЄҐўЎ]',value):return False
    return bool(letters) and len(re.findall('[а-яёА-ЯЁ]',value)) / len(letters)>.65


def chunks(value):
    """Keep paragraph/sentence context and every character, even oversized prose."""
    while len(value)>CHUNK:
        end=value.rfind('\n\n',0,CHUNK)
        if end>=CHUNK//3:end+=2
        else:
            boundaries=list(re.finditer(r'[.!?][”’\"\']?\s+',value[:CHUNK]))
            end=boundaries[-1].end() if boundaries and boundaries[-1].end()>=CHUNK//3 else value.rfind(' ',0,CHUNK)+1
        if end<1:end=CHUNK
        yield value[:end];value=value[end:]
    if value:yield value


def translate_text(value, opener=urllib.request.urlopen, alive=lambda:True):
    original=clean(value)
    if is_russian(original):return original
    output=[]
    for part in chunks(original):
        if not alive():raise TranslationError('Cancelled')
        # POST avoids putting editorial prose in URLs. Never attach service
        # cookies, a user's browser headers, tokens or account identifiers.
        body=urllib.parse.urlencode({'client':'gtx','sl':'auto','tl':'ru','dt':'t','q':part}).encode('utf-8')
        request=urllib.request.Request(ENDPOINT,data=body,headers={
            'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8',
            'User-Agent':'Emberbox-Audio/Editorial-Reader'})
        try:
            with opener(request,timeout=12) as response:
                raw=response.read(MAX_REPLY+1)
            if len(raw)>MAX_REPLY:raise TranslationError('Reply too large')
            data=json.loads(raw)
            rows=data[0] if isinstance(data,list) and data else None
            if not isinstance(rows,list) or not rows:raise TranslationError('Invalid reply')
            # All segments must be present. Never display a partial biography
            # as a successfully translated complete article.
            if any(not isinstance(row,list) or len(row)<2 or
                   not isinstance(row[0],str) or not isinstance(row[1],str) for row in rows):
                raise TranslationError('Incomplete reply')
            result=''.join(row[0] for row in rows)
            source=''.join(row[1] for row in rows)
            if ''.join(source.split())!=''.join(part.split()) or not result.strip():
                raise TranslationError('Incomplete reply')
            # Some responses trim the trailing paragraph/space boundary.
            trailing=part[len(part.rstrip()):]
            output.append(result.rstrip()+trailing)
        except TranslationError:raise
        except Exception as exc:raise TranslationError('Translation unavailable') from exc
    result=CONTROL.sub('', ''.join(output)).strip()
    if not result or len(result)>MAX_TEXT*4:raise TranslationError('Invalid translation')
    return result


class TranslationCache:
    """Small exact-content cache; disk access happens only in the worker."""
    def __init__(self,folder=None):
        self.folder=Path(folder) if folder is not None else CACHE_DIR/'editorial-translations'
        self.memory=OrderedDict();self.lock=threading.Lock()

    def remembered(self,value):
        with self.lock:
            result=self.memory.get(identity(value))
            return result

    def remember(self,value,result):
        with self.lock:
            key=identity(value);self.memory[key]=result;self.memory.move_to_end(key)
            while len(self.memory)>48:self.memory.popitem(last=False)

    def read(self,value):
        hit=self.remembered(value)
        if hit:return hit
        try:
            path=self.folder/(identity(value)+'.json')
            if path.stat().st_size>256_000:return None
            record=json.loads(path.read_text())
            result=record['translation']
            if (record['source']!=value or record['provider']!=PROVIDER or
                not 0<=time.time()-record['created']<TTL or not isinstance(result,str) or
                not result.strip() or len(result)>MAX_TEXT*4):return None
            result=CONTROL.sub('',result)
            self.remember(value,result);return result
        except (OSError,ValueError,KeyError,TypeError):return None

    def write(self,value,result):
        self.remember(value,result)
        temporary=None
        try:
            self.folder.mkdir(mode=0o700,parents=True,exist_ok=True)
            target=self.folder/(identity(value)+'.json')
            temporary=target.with_suffix('.tmp')
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as handle:
                json.dump({'provider':PROVIDER,'source':value,'translation':result,'created':time.time()},handle,ensure_ascii=False)
            temporary.replace(target)
            entries=sorted(self.folder.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
            for old in entries[64:]:old.unlink(missing_ok=True)
        except OSError:pass  # Read-only/full cache storage cannot break reading.
        finally:
            if temporary:
                try:temporary.unlink(missing_ok=True)
                except OSError:pass


class EditorialTranslator:
    """One low-impact worker; bounded and deduplicated user-initiated jobs."""
    def __init__(self,cache=None,translate=translate_text,dispatch=None):
        if dispatch is None:
            from gi.repository import GLib
            dispatch=GLib.idle_add
        self.cache=cache or TranslationCache();self.translate=translate;self.dispatch=dispatch
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='ember-reader')
        self.jobs={};self.preferred=set();self.closed=False

    def request(self,value,callback):
        value=clean(value);key=identity(value);token=object()
        if self.closed:return lambda:None
        self.preferred.add(key)
        if key in self.jobs:
            listeners=self.jobs[key][1];listeners[token]=callback
        else:
            if len(self.jobs)>=4:
                self.dispatch(lambda:(callback(None,TranslationError('Busy')),False)[1])
                return lambda:None
            listeners={token:callback}
            def work():
                if self.closed:raise TranslationError('Cancelled')
                hit=self.cache.read(value)
                if hit:return hit
                result=self.translate(value,alive=lambda:not self.closed)
                if not self.closed:self.cache.write(value,result)
                return result
            future=self.pool.submit(work)
            self.jobs[key]=(future,listeners)
            def finished(future):
                try:result,error=future.result(),None
                except Exception:result,error=None,TranslationError('Translation unavailable')
                def deliver():
                    self.jobs.pop(key,None)
                    if not self.closed:
                        for listener in tuple(listeners.values()):listener(result,error)
                    listeners.clear();return False
                self.dispatch(deliver)
            future.add_done_callback(finished)
        return lambda:listeners.pop(token,None)

    def prefer(self,value,translated):
        if translated:self.preferred.add(identity(value))
        else:self.preferred.discard(identity(value))

    def close(self):
        self.closed=True
        for _future,listeners in self.jobs.values():listeners.clear()
        self.jobs.clear();self.preferred.clear();self.pool.shutdown(wait=False,cancel_futures=True)
