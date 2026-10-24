"""Small local-model contract: describe a search, never invent playable music."""
from dataclasses import replace
import re
from dj_intent import Intent,clean,wish_text,REQUEST_PREFIX,artist_key,local_intent
from source_picker import text

SCHEMA={'type':'object','properties':{
    'kind':{'type':'string','enum':['mix','artist','track','similar','clarify']},
    'query':{'type':'string','maxLength':64}},
    'required':['kind','query'],'additionalProperties':False}
SYSTEM='''Interpret musical wishes. JSON only: kind (mix,artist,track,similar,clarify), query.
mix: ONE playlist search of 2-5 English music keywords describing SOUND, not literal scenery. Jumping=energetic dance; noir=dark cinematic jazz; weightless=ethereal ambient.
artist/track/similar: exact explicitly requested name. clarify: unclear or nonmusical.
Previous exists only for follow-ups: keep its sound, apply changes and negation. No previous means a fresh wish. No invented names, IDs, explanations or lists.'''

CAPTIONS=(
 (r'noir',('Noir atmosphere','Атмосфера нуара')),
 (r'energetic|energy|upbeat|workout',('More energy','Больше энергии')),
 (r'dance|party|disco',('Dance rhythms','Танцевальный ритм')),
 (r'ethereal|weightless|floating|dreamy',('Weightless sound','Невесомое звучание')),
 (r'cinematic|soundtrack',('A cinematic atmosphere','Кинематографичная атмосфера')),
 (r'focus|study|concentrat',('Space to concentrate','Пространство для мыслей')),
 (r'warm|cozy|mellow',('A warmer sound','Тёплое звучание')),
 (r'calm|chill|relax|gentle|soft',('A gentler sound','Мягкое звучание')),
 (r'vintage|vinyl|retro|analog|\bold\b',('Vintage warmth','Винтажное тепло')),
 (r'nostalg|melanchol|moody|\bsad\b',('A reflective mood','Задумчивое настроение')),
 (r'jazz',('Jazz','Джаз')),(r'ambient',('Ambient','Эмбиент')),
 (r'lounge',('Lounge','Лаунж')),(r'synthwave',('Synthwave','Синтвейв')),
 (r'lo.?fi',('Lo-fi','Лоу-фай')),(r'piano',('Piano','Фортепиано')),
 (r'acoustic',('Acoustic sound','Акустическое звучание')),(r'rock',('Rock','Рок')),
 (r'soul',('Soul','Соул')),(r'electronic',('Electronic sound','Электроника')),
 (r'\bpop\b',('Pop','Поп')),(r'romantic|romance',('A romantic mood','Романтическое настроение')),
 (r'night (?:drive|road)|nightdrive',('Night drive','Ночная дорога')),
 (r'rain',('Rainy atmosphere','Дождливая атмосфера')),
 (r'winter|snow',('A winter atmosphere','Зимняя атмосфера')),
 (r'night',('After dark','После заката')))


def caption_for(query):
    parts=[]
    for pattern,labels in CAPTIONS:
        if re.search(pattern,query,re.I):
            value=text(*labels)
            if len(' · '.join(parts+[value]))<=64:parts.append(value)
        if len(parts)==3:break
    return ' · '.join(parts) or clean(query,64)

NO_SINGING=(r'без\s+(?:\w+\s+)?(?:пени\w*|вокал\w*|слов|голос\w*)|'
    r'(?:никто|никого).{0,20}(?:не\s+(?:пел\w*|поет|поют|петь)|поющ)|'
    r'(?:чтобы|чтоб|пусть).{0,20}не\s+(?:пел\w*|петь|поют)|'
    r'(?:только|одни)\s+(?:музыкальные\s+)?инструмент\w*|'
    r'no(?:body| one).{0,20}sing|only (?:the )?instruments|no singing|without singing')
WITH_SINGING=r'верни\s+(?:вокал|голос)|со?\s+(?:пением|вокалом|голосом)|with (?:singing|vocals)|bring back (?:the )?(?:voice|vocals)|bring (?:the )?(?:singing|vocals|voice) back'


def follows(prompt):
    value=re.sub(REQUEST_PREFIX,'',wish_text(prompt).casefold().replace('ё','е'),flags=re.I)
    if re.search(r'с чистого листа|совсем другое|заново|новый сет|new station|start over',value):return False
    return bool(re.search(r'^(?:а\b|но\b|теперь\b|еще\b|в том же|в этом же|так же|то же|все (?:это|так|то)|'
        r'тот же|та же|ту же|того же|такой же|такая же|оставь|сохрани|добавь|убери|поменьше|побольше|больше|меньше|немного|чуть|по\w+ее\b|'
        r'сделай|пусть|потом|вместо|без\b|с вокалом|same|keep|make|add|less|more|without|with|instead|that)',value) or
        re.search(r'\b(?:их же|они же|таком же духе|том же духе|этом же духе|то же самое|the same|same artist|by them)\b',value))


def context(previous):
    if previous is None:return {}
    return {k:v for k,v in {'query':previous.search or previous.query,'caption':previous.caption,
        'mode':previous.mode,'artists':list(previous.artists),'mood':previous.mood,
        'instrumental':previous.instrumental,'avoid':list(previous.avoid)}.items() if v not in ('',[],None,'any')}


def clarify(message=None):
    return Intent(action='clarify',question=message or text(
        'What atmosphere or kind of music would you like?','Какое настроение или звучание хочется услышать?'))


def vocal_followup(prompt,previous):
    """A fully covered vocal-only change needs neither inference nor a new scene."""
    if previous is None or not follows(prompt):return None
    value=wish_text(prompt).casefold().replace('ё','е')
    silent=bool(re.search(NO_SINGING,value));singing=bool(re.search(WITH_SINGING,value))
    if silent==singing:return None
    rest=re.sub(NO_SINGING+'|'+WITH_SINGING,' ',value)
    rest=re.sub(r'\b(?:в (?:этом|том) же духе|то же самое|так же|same (?:feeling|atmosphere|sound)|'
        r'keep (?:the )?(?:same )?(?:feeling|atmosphere|sound))\b',' ',rest)
    if any(w not in ('а','но','теперь','чтобы','чтоб','пусть','только','пожалуйста','и','давай','это','все',
                    'but','now','please','and','just','it') for w in re.findall(r'\w+',rest)):return None
    return replace(previous,instrumental=silent,action='mix',question='')


def decode(data,prompt,previous,fallback):
    if not isinstance(data,dict):raise ValueError('Invalid musical interpretation')
    if set(data)-set(SCHEMA['properties']):raise ValueError('Unexpected musical interpretation fields')
    kind=data.get('kind');query=clean(data.get('query'),80)
    if kind not in SCHEMA['properties']['kind']['enum'] or not query:raise ValueError('Missing musical interpretation')
    if re.search(r'https?://|\b(?:spotify|apple|youtube|file):|[{}<>\n]',query,re.I):raise ValueError('Not a music search')
    if re.search(r'playlist keywords|english (?:playlist|search)|json|system prompt|instructions',query,re.I):raise ValueError('Instruction instead of a search')
    base=previous if previous is not None and follows(prompt) else Intent()
    if kind=='clarify':return clarify()
    value=wish_text(prompt).casefold().replace('ё','е')
    if previous is None and re.search(r'как раньше|как до этого|то же самое|в том же духе|same as before|the same',value):return clarify()
    instrumental=base.instrumental
    if re.search(r'\binstrumentals?\b|\b(?:no|without) vocals\b',query,re.I):instrumental=True
    elif re.search(r'\b(?:vocals|singing)\b',query,re.I):instrumental=False
    if re.search(NO_SINGING,value):instrumental=True
    elif re.search(WITH_SINGING,value):instrumental=False
    elif fallback.instrumental is not None and fallback.instrumental!=base.instrumental:instrumental=fallback.instrumental
    avoid=tuple(dict.fromkeys(base.avoid+fallback.avoid))
    if kind in ('artist','track','similar'):
        norm=lambda s:re.sub(r'[^\w]+',' ',str(s).casefold()).strip()
        grounded=(' '+norm(query)+' ') in (' '+norm(prompt)+' ') or any(artist_key(query)==artist_key(word) for word in re.findall(r'\w+',prompt))
        grounded=grounded or bool(base.query and artist_key(query)==artist_key(base.query)) or any(artist_key(query)==artist_key(a) for a in base.artists)
        if not grounded:raise ValueError('Unmentioned artist or title')
        words=re.findall(r'\w+',query)
        if norm(query)==norm(prompt) and len(words)>1 and not all(w[:1].isupper() for w in words):
            raise ValueError('A conversation is not a literal title')
        return Intent(mood=fallback.mood,genres=fallback.genres,artists=(query,) if kind!='track' else (),
            avoid=avoid,instrumental=instrumental,familiarity=base.familiarity,query=query,
            mode={'artist':'artist','track':'lookup','similar':'similar'}[kind])
    # Some compact models return several candidate searches. Keep one coherent
    # phrase; combining unrelated alternatives makes catalogue searches empty.
    alternatives=[clean(p,64) for p in re.split(r'[,;|\n]',query) if clean(p)]
    if not alternatives:raise ValueError('No musical search')
    if base.search:
        words=set(re.findall(r'\w+',base.search.casefold()))
        query=max(alternatives,key=lambda p:len(words.intersection(re.findall(r'\w+',p.casefold()))))
        if re.search(NO_SINGING,value) or re.search(WITH_SINGING,value):query=base.search
        elif len(words.intersection(re.findall(r'\w+',query.casefold())))==0:
            query=base.search+' '+alternatives[0]
    else:query=alternatives[0]
    query=' '.join(query.split()[:8])
    if len(query.split())>12:raise ValueError('Search is not concise')
    # The model proposes a sound, while explicit exclusions remain authoritative.
    for word in avoid:query=re.sub(r'\b'+re.escape(word)+r'\b',' ',query,flags=re.I)
    query=clean(query,80)
    if not query:raise ValueError('Conflicting musical constraints')
    if instrumental is False:query=re.sub(r'\binstrumental(?:s)?\b','',query,flags=re.I).strip()
    # Explicit anaphora keep an artist-only station; a generic new mood releases it.
    if base.mode=='artist' and base.artists and re.search(r'\b(?:их|они|этого исполнителя|этой группы|same artist|by them)\b',value):
        return replace(base,mood=fallback.mood,avoid=avoid,instrumental=instrumental)
    inferred=local_intent(query)
    mood=inferred.mood if inferred.mood!='any' else fallback.mood if fallback.mood!='any' else base.mood
    genres=fallback.genres or base.genres
    return Intent(mood=mood,genres=genres,avoid=avoid,instrumental=instrumental,
        familiarity=.2 if mood=='discover' else base.familiarity,search=query,caption=caption_for(query))
