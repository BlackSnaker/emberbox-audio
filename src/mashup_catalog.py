"""Small, on-demand ccMixter catalogue; no account, scraping or paid streams.

Only CC BY audio hosted by ccMixter is accepted. Re-resolve IDs immediately
before preparation. Neither saved projects nor catalogue descriptions can
provide decoder URLs or broaden the allowed hosts.
"""
from collections import OrderedDict
import html
import json
import re
import time
import urllib.parse
import urllib.request

API='https://ccmixter.org/api/query'
MAX_BYTES=2_000_000
MAX_FILE=50*1024*1024
PAGE_SIZE=5  # Legacy ccHost duplicates JSON into an X-JSON response header.


def words(value,limit=300):
    return re.sub(r'[\x00-\x1f\x7f]',' ',html.unescape(str(value or ''))).strip()[:limit]


def license_url(value):
    try:p=urllib.parse.urlsplit(str(value))
    except ValueError:return ''
    if p.hostname not in ('creativecommons.org','www.creativecommons.org'):return ''
    if not re.fullmatch(r'/licenses/by/(?:1\.0|2\.0|2\.5|3\.0|4\.0)/?',p.path):return ''
    return 'https://creativecommons.org'+p.path.rstrip('/')+'/'


def source_page(value,ident):
    try:p=urllib.parse.urlsplit(str(value))
    except ValueError:return ''
    if p.hostname not in ('ccmixter.org','www.ccmixter.org'):return ''
    if not re.fullmatch(r'/files/[\w.-]+/'+re.escape(str(ident)),p.path):return ''
    return 'https://ccmixter.org'+p.path


def media_url(value):
    try:
        p=urllib.parse.urlsplit(str(value));port=p.port
    except ValueError:return ''
    if (p.scheme!='https' or p.hostname not in ('ccmixter.org','www.ccmixter.org') or
        p.username or p.password or port not in (None,443) or p.query or p.fragment):return ''
    path=urllib.parse.unquote(p.path)
    if not re.fullmatch(r'/content/[\w.-]+/[^/]+\.(?:mp3|ogg|flac|wav|m4a)',path,re.I):return ''
    if any(part in ('.','..') for part in path.split('/')):return ''
    return urllib.parse.urlunsplit(('https',p.netloc,p.path,'',''))


def seconds(value):
    try:
        fields=str(value).split(':')
        total=0.
        for part in fields:total=total*60+float(part)
        return total if 0<total<=600 else 0.
    except (ValueError,TypeError):return 0.


def record(raw):
    if not isinstance(raw,dict):return None
    lic=license_url(raw.get('license_url'))
    ident=str(raw.get('upload_id',''))
    if not lic or not re.fullmatch(r'\d{1,12}',ident):return None
    extra=raw.get('upload_extra') or {}
    if extra.get('nsfw') is True:return None
    tags=set(filter(None,str(raw.get('upload_tags','')).lower().split(',')))
    for file in raw.get('files') or []:
        try:
            size=int(file.get('file_rawsize') or 0)
            url=media_url(file.get('download_url'))
            if not url or file.get('file_is_remote') or not 0<size<=MAX_FILE:continue
            duration=seconds((file.get('file_format_info') or {}).get('ps'))
            if not duration:continue
            try:bpm=float(extra.get('bpm') or 0)
            except (ValueError,TypeError):bpm=0.
            if not 40<=bpm<=250:bpm=0.
            user=words(raw.get('user_name'),80)
            if not re.fullmatch(r'[\w.-]+',user):return None
            title=words(raw.get('upload_name'));artist=words(raw.get('user_real_name') or user)
            if not title or not artist:return None
            return {'source':'ccmixter','id':ident,'title':title,
                'artist':artist,'page':f'https://ccmixter.org/files/{user}/{ident}',
                'license':lic,'url':url,'duration':duration,'bpm':bpm,
                'kind':'vocal' if tags&{'acappella','a_cappella','pella'} else 'instrumental' if 'instrumental' in tags else 'song',
                'credits':words(extra.get('featuring'),500),
                'notes':words(raw.get('upload_description_plain'),2500)}
        except (ValueError,TypeError,AttributeError):continue
    return None


class Catalog:
    def __init__(self,opener=urllib.request.urlopen):self.opener=opener;self.cache=OrderedDict()

    def read(self,params):
        query=urllib.parse.urlencode({'f':'json','lic':'by','limit':PAGE_SIZE,**params})
        request=urllib.request.Request(API+'?'+query,headers={'User-Agent':'Emberbox-Audio/Mashups (+https://github.com/BlackSnaker/emberbox-audio)'})
        with self.opener(request,timeout=12) as response:raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError('catalogue-too-large')
        rows=json.loads(raw)
        if not isinstance(rows,list):raise ValueError('catalogue-invalid')
        return [v for row in rows[:25] if (v:=record(row))]

    def search(self,term='',kind='song',page=0):
        term=words(term,160);page=max(0,min(10,int(page)))
        key=(term,kind,page);cached=self.cache.get(key)
        if cached and time.monotonic()-cached[0]<1800:return cached[1]
        params={'offset':page*PAGE_SIZE}
        if term:params['search']=term
        if kind=='vocal':params['tags']='acappella'
        elif kind=='instrumental':params['tags']='instrumental'
        result=self.read(params);self.cache[key]=(time.monotonic(),result)
        while len(self.cache)>24:self.cache.popitem(last=False)
        return result

    def resolve(self,item):
        if item.get('source')!='ccmixter':raise ValueError('source-not-editable')
        ident=str(item.get('id',''))
        if not re.fullmatch(r'\d{1,12}',ident):raise ValueError('catalogue-invalid-id')
        values=self.read({'ids':ident,'limit':1})
        result=next((v for v in values if v['id']==ident),None)
        if result is None:raise ValueError('track-unavailable')
        return result
