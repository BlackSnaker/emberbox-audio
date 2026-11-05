"""Private mashup recipes. No audio, service credentials or decoder URLs."""
import json
import math
import os
from pathlib import Path
import tempfile
import uuid
from paths import CONFIG_DIR
from mashup_catalog import words,license_url,source_page


def number(value,low,high,default):
    try:
        value=float(value)
        return max(low,min(high,value)) if math.isfinite(value) else default
    except (ValueError,TypeError):return default


def recipe(raw):
    if not isinstance(raw,dict):raise ValueError('project-invalid')
    result={'id':words(raw.get('id'),40),'name':words(raw.get('name'),100),'tracks':[]}
    for value in list(raw.get('tracks') or [])[:2]:
        if not isinstance(value,dict):raise ValueError('project-invalid-track')
        source=words(value.get('source'),40)
        if source not in ('ccmixter','apple-music','spotify','yandex-music','youtube'):raise ValueError('project-invalid-source')
        role=value.get('role','song')
        if role not in ('vocal','instrumental','song'):raise ValueError('project-invalid-role')
        result['tracks'].append({'source':source,'id':words(value.get('id'),160),
            'title':words(value.get('title')),'artist':words(value.get('artist')),
            'page':source_page(value.get('page',''),value.get('id','')) if source=='ccmixter' else '',
            'license':license_url(value.get('license','')),'credits':words(value.get('credits'),500),
            'notes':words(value.get('notes'),2500),'role':role,
            'start':number(value.get('start'),0,599,0),'gain':number(value.get('gain'),0,1.5,.75)})
    result.update(whole=raw.get('whole') is True,length=number(raw.get('length'),5,120,30),
        auto=raw.get('auto',True) is True,tempo=number(raw.get('tempo'),0,200,0),
        shift=round(number(raw.get('shift'),-6,6,0)),offset=number(raw.get('offset'),-10,10,0))
    return result


class Projects:
    def __init__(self,path=None):
        self.path=Path(path) if path is not None else CONFIG_DIR/'mashups.json'
        self.items=[];self.error=''
        try:
            if self.path.exists():
                if self.path.stat().st_size>500_000:raise ValueError('project-store-too-large')
                data=json.loads(self.path.read_text())
                if data.get('version')!=1 or not isinstance(data.get('projects'),list):raise ValueError('project-store-invalid')
                self.items=[recipe(v) for v in data['projects'][:24]]
        except (OSError,ValueError,TypeError,AttributeError):self.error='project-store-invalid'

    def save(self,value):
        if self.error:raise ValueError(self.error)
        item=recipe(value)
        if not item['id']:item['id']=uuid.uuid4().hex
        items=[item]+[v for v in self.items if v['id']!=item['id']]
        if len(items)>24:raise ValueError('project-limit')
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        temporary=None
        try:
            with tempfile.NamedTemporaryFile('w',dir=self.path.parent,prefix='.mashups-',delete=False) as handle:
                temporary=Path(handle.name);os.chmod(temporary,0o600)
                json.dump({'version':1,'projects':items},handle,ensure_ascii=False)
            temporary.replace(self.path);self.items=items
        finally:
            if temporary:temporary.unlink(missing_ok=True)
        return item
