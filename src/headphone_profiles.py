"""Small offline, attributed headphone presets; no brand-based guessing."""
from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def catalogue():
    return json.loads((Path(__file__).parent/'apple_web_host/headphone_profiles.json').read_text())['profiles']


def settings(value=None):
    value=value or {}
    result={'profile':value.get('profile','none'),'strength':value.get('strength',100),
            'bass':value.get('bass',0),'treble':value.get('treble',0),
            'balance':value.get('balance',0),'bypass':value.get('bypass',False)}
    if result['profile'] not in {p['id'] for p in catalogue()} or type(result['bypass']) is not bool:
        raise ValueError('Invalid headphone settings')
    for key,low,high in [('strength',0,100),('bass',-4,4),('treble',-4,4),('balance',-20,20)]:
        if type(result[key]) is not int or not low<=result[key]<=high:raise ValueError('Invalid headphone settings')
    return result


def profile(ident):
    return next(p for p in catalogue() if p['id']==ident)
