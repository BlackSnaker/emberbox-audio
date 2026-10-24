"""Bounded musical intent; model output can describe a mix, never invent tracks."""
from dataclasses import dataclass,asdict,replace
import re,unicodedata

INDEFINITE_ROOT=r'(?:что|чего|чему|чем|кто|кого|кому|кем|какая|какой|какое|какую|какие|каких|какого|какому|каким|какими|где|куда|когда)'
INDEFINITE=INDEFINITE_ROOT+r'-(?:нибудь|либо|то)'
REQUEST_PREFIX=(r'^(?:(?:я|мне|хочу|хочется|нужно|надо|бы|пожалуйста|можно|только|'
    r'ну|а|так|да|слушай|пожалуй|может(?: быть)?|давай(?:-ка)?|дай|подбери|собери|накидай|насыпь|'
    r'включи|поставь|найди|ищи|послушать|слушать|послушаем|play|find|search for|please|i want|listen to)(?:\s+|,\s*))+')

MOODS=('any','relax','focus','happy','energy','party','romance','melancholy','discover')
MOOD_WORDS={
    'relax':r'расслаб|спокой|отдох|чилл|успок|помягче|помедленнее|полегче|нежн|перед сном|заснут|для сна|chill|relax|calm|unwind|softer|slower|sleep|wind down',
    'focus':r'сосредоточ|фокус|работ[аыуе]|уч[её]б|кодить|программиров|для чтения|focus|study|concentrat|\bwork\b|coding|reading',
    'happy':r'весел|радост|позитив|жизнерадост|подн\w* настроен|поднять мне настроение|развесел|cheerful|happ(?:y|ier)|upbeat|uplift|feel.good|cheer me up',
    'energy':r'бодр|энерги|заряд|трениров|проснут|поживее|живее|побыстрее|драйв|energy|energetic|workout|wake up|livelier|faster|more lively',
    'party':r'танц|вечерин|дискотек|dance|party',
    'romance':r'романти|свидани|romantic|date night',
    'melancholy':r'груст|меланхол|погруст|melanchol|sad',
    'discover':r'открыти|новеньк|новое|незнаком|необыч|друго[ейую]|другое|разнообраз|удиви|discover|something new|new music|something else|different|surprise me|change it up'}
GENRES={
    'indie':r'инди|\bindie\b','psychedelic':r'психодел|psychedelic',
    'jazz':r'джаз|\bjazz\b','blues':r'блюз|\bblues\b','rock':r'\bрок\w*|\brock\b',
    'metal':r'метал|потяжелее|пожестче|\bmetal\b|heavier','ambient':r'эмбиент|амбиент|\bambient\b',
    'electronic':r'электрон|electronic','classical':r'классик|classical',
    'hip hop':r'хип.хоп|\bрэп\w*|hip.hop|\brap\b','pop':r'\bпоп(?:а|е|ом)?\b|\bpop\b',
    'soul':r'соул|\bsoul\b','funk':r'фанк|\bfunk\b','lofi':r'лоу.?фай|ло.?фай|lo.?fi',
    'acoustic':r'акустик|acoustic','folk':r'фолк|\bfolk\b','techno':r'техно|\btechno\b',
    'house':r'хаус|\bhouse\b','reggae':r'регги|reggae','r&b':r'ритм.энд.блюз|\br.?n.?b\b'}
ACTIONS={
    'like':r'^(?:это )?(?:нравится|люблю это|классный трек|запомни это|like|love this)(?:[.! ]*)$',
    'dislike':r'^(?:это )?(?:не мо[её]|не нравится|не хочу это|dislike|not for me)(?:[.! ]*)$',
    'next':r'^(?:дальше|следующ(?:ий|ая|ее)|пропусти(?: трек)?|next|skip)(?:[.! ]*)$',
    'pause':r'^(?:пауза|останови(?: музыку)?|pause|stop music)(?:[.! ]*)$',
    'resume':r'^(?:продолжи(?: музыку)?|resume|continue music)(?:[.! ]*)$'}


def clean(value,limit=80):return re.sub(r'\s+',' ',str(value or '')).strip()[:limit]


def wish_text(value):
    """Normalize conversational spelling, without rewriting the displayed wish."""
    value=unicodedata.normalize('NFKC',str(value or ''))[:2000]
    value=re.sub('[\u200b\ufeff\u00ad]','',value)
    # ASR and keyboards produce "что - нибудь", NBSPs and Unicode dashes.
    # Only join known indefinite pronouns; keep artist/title hyphens intact.
    return clean(re.sub(r'\b('+INDEFINITE_ROOT+r')[\s\-\u2010-\u2015\u2212]*(нибудь|либо|то)\b',
        lambda m:m[1]+'-'+m[2],value,flags=re.I),500)


def exact_target(prompt):
    """Explicit title searches may themselves contain conversational words."""
    value=clean(prompt,500)
    value=re.sub(REQUEST_PREFIX,'',value,flags=re.I)
    quoted=re.fullmatch(r'(?:(?:трек|песню|песни|композицию|song|track)(?:\s+под названием)?\s+)?[«"“](.+?)[»"”][.!?]*',value,re.I)
    if quoted:return clean(quoted[1],160)
    named=re.fullmatch(r'(?:трек|песню|композицию|song|track)\s+(?:под названием|с названием|called|named)\s+(.+)',value,re.I)
    if named:return clean(named[1],160)
    return ''


@dataclass(frozen=True)
class Intent:
    mood:str='any'
    genres:tuple=()
    artists:tuple=()
    avoid:tuple=()
    instrumental:bool|None=None
    familiarity:float=.65
    action:str='mix'
    query:str=''
    mode:str='mix'
    search:str=''
    caption:str=''
    question:str=''
    def data(self):return asdict(self)


def local_intent(prompt,previous=None):
    exact=exact_target(prompt)
    if exact:return Intent(query=exact,mode='lookup')
    prompt=wish_text(prompt)
    value=prompt.casefold().replace('ё','е')
    same_scope=bool(re.search(r'\b(?:их|они|этого исполнителя|этой группы|в этом же духе|same artist|by them|their songs)\b',value))
    followup=same_scope or bool(re.search(r'^(?:а |но |теперь |давай |еще|больше|меньше|по\w+ее\b|чуть|немного |без |с вокалом|more |less |calmer|without |with vocals|something |make it )',value))
    base=(previous or Intent()) if followup else Intent()
    if re.search(r'совсем другое|с чистого листа|start over|different style',value):base=Intent()
    for action,pattern in ACTIONS.items():
        if re.search(pattern,value):return replace(base,action=action)
    # Remove explicit exclusions before detecting positive genres/moods.
    exclusion=r'(?:\bбез\b|\bне хочу\b|\bне\b|\bкроме\b|\bno\b|\bnot\b|\bwithout\b)\s+([^,.;]+?)(?=,|[.;]|\s+(?:но|а|but)\s+|$)'
    excluded=re.findall(exclusion,value)
    positive=re.sub(exclusion,' ',value)
    genres=tuple(key for key,pattern in GENRES.items() if re.search(pattern,positive))
    avoid=tuple(key for key,pattern in GENRES.items() if any(re.search(pattern,part) for part in excluded))
    # A last explicit correction wins: "не грустное, а повеселее".
    matches=[(match.start(),key) for key,pattern in MOOD_WORDS.items() for match in re.finditer(pattern,positive)]
    explicit_mood=max(matches,default=(-1,''))[1]
    if not explicit_mood and any(re.search(MOOD_WORDS['melancholy'],part) for part in excluded):explicit_mood='happy'
    if not explicit_mood and any(re.search(MOOD_WORDS['energy'],part) for part in excluded):explicit_mood='relax'
    mood=explicit_mood or base.mood
    instrumental=base.instrumental
    if re.search(r'без (?:вокала|слов|голоса)|инструменталь|instrumental|no vocals|without (?:vocals|lyrics)',value):instrumental=True
    elif re.search(r'с вокалом|с голосом|with vocals',value):instrumental=False
    familiarity=.2 if mood=='discover' else .85 if re.search(r'любим|знаком|familiar|favourites|favorites',value) else base.familiarity
    artists=()
    similar=re.search(r'(?:как|в стиле|похож[а-я]* на|like|similar to)\s+(.{2,80}?)(?=,|\s+(?:но|только|без|but|without)\b|$)',clean(prompt,500),re.I)
    if similar:artists=(similar.group(1).strip(),)
    stripped=clean(prompt,160).strip(' \"«»')
    stripped=re.sub(REQUEST_PREFIX,'',stripped,flags=re.I)
    stripped=re.sub(r'^(?:(?:музык[ауи]|песни|песен|треки|треков|групп[уы]|исполнител[ья]|music by|songs by|tracks by|band|artist)\s+)+','',stripped,flags=re.I).strip(' \"«»')
    stripped=re.sub(r'(?:,?\s+пожалуйста|,?\s+please|\s+без рекомендаций|\s+без других исполнителей)[.!?]*$', '', stripped, flags=re.I).strip()
    # Keep a named target separate from its musical qualifier. Do not search
    # for the whole sentence "Beatles, но повеселее" as a song title.
    target=re.sub(exclusion,' ',stripped,flags=re.I)
    target=re.sub(r'\b(?:с (?:вокалом|голосом)|with vocals|инструменталь\w*|instrumental)\b',' ',target,flags=re.I)
    unmasked=target
    spans=[]
    for pattern in (*MOOD_WORDS.values(),*GENRES.values()):
        for match in re.finditer(pattern,target,flags=re.I):
            start=match.start()-len(re.search(r'\w*$',target[:match.start()]).group())
            end=match.end()+len(re.match(r'\w*',target[match.end():]).group())
            spans.append((start,end))
    for start,end in sorted(spans,reverse=True):target=target[:start]+' '*(end-start)+target[end:]
    target=re.sub(exclusion,' ',target,flags=re.I)
    filler=r'\b(?:'+INDEFINITE+r'|музык\w*|песни|песен|треки|треков|немного|побольше|поменьше|чуть|еще|ещё|теперь|пожалуйста|сделай|давай|более|менее|очень|чуточку|лучше|хотелось|хочется|нужн\w*|надо|как|но|а|и|для|меня|мне|на|от|бы|в|же|они|их|этого|исполнителя|этой|группы|этом|духе|звучании|вкусе|моем|моём|something|anything|music|songs|tracks|a|bit|more|less|some|it|make|please|but|and|by|of|them|same|artist|to|for|me)\b'
    tidy=lambda s:clean(re.sub(filler,' ',s,flags=re.I)).strip(' ,.!?:;—-')
    # Only a leading name or an explicit "от / by" is an artist qualifier.
    # Leftover conversational words after a mood are not a second exact search.
    lead=tidy(unmasked[:min(start for start,_ in spans)]) if spans else tidy(target)
    by=re.search(r'\b(?:от|by)\s+([^,;]+)',unmasked,re.I)
    target=tidy(by.group(1)) if by else lead
    vocal_wish=bool(re.search(r'без (?:вокала|слов|голоса)|инструменталь|instrumental|no vocals|without (?:vocals|lyrics)|с вокалом|с голосом|with vocals',value))
    qualified_target=target if (explicit_mood or genres or avoid or vocal_wish) and target else ''
    # A comparative mood changes the station; an explicit name or "их же"
    # keeps the artist. Plain "ещё" also continues the previous station.
    continuation=bool(re.fullmatch(r'(?:а )?(?:еще|ещё|more|побольше|продолжай|keep going|another one)[.!? ]*',value))
    if explicit_mood=='discover' and not same_scope:
        base=Intent(avoid=base.avoid)
        if not vocal_wish:instrumental=None
    if explicit_mood and not same_scope and base.mode in ('artist','lookup','similar'):
        base=Intent(avoid=base.avoid)
        if not re.search(r'без (?:вокала|слов|голоса)|instrumental|without vocals',value):instrumental=None
    # A named target must survive generic words such as "music" in the wish.
    known=bool(genres or avoid or explicit_mood or vocal_wish)
    generic=bool(re.fullmatch(r'(?:музык[ауи]|music|микс|mix|моя волна|в мо[её]м вкусе|'+INDEFINITE+r'|something)(?: в мо[её]м вкусе)?',stripped,re.I))
    query=artists[0] if similar else qualified_target or ('' if known or generic else stripped)
    mode='similar' if similar else 'lookup' if query else 'mix'
    if query and not similar and not qualified_target and re.search(INDEFINITE+r'|(?:музык\w*|песни|трек\w*) (?:для|под)|\b(?:music for|music to|something|anything)\b',value):
        # An unfamiliar occasion/style can still use the source's playlist
        # search. It must not enter the exact artist/song relevance filter.
        mode='theme';query=re.sub(r'^(?:'+INDEFINITE+r'|something|anything)\s*','',stripped,flags=re.I).strip()
    if previous and not similar and not qualified_target and (continuation or same_scope or
            followup and not explicit_mood and not genres and (avoid or instrumental is not None)):
        query=base.query;mode=base.mode;artists=base.artists
    if mode=='lookup' and not qualified_target and not continuation and not same_scope:base=Intent();mood='any';instrumental=None
    result=Intent(mood,genres or base.genres,artists,tuple(dict.fromkeys(base.avoid+avoid)),
                  instrumental,familiarity,'mix',query,mode)
    if previous and (continuation or followup and not explicit_mood and not genres and not qualified_target):
        result=replace(result,search=base.search,caption=base.caption)
    return result



def quick_wish(prompt,previous=None,intent=None):
    """Only fully covered wishes bypass inference; length is not confidence."""
    value=wish_text(prompt).casefold().replace('ё','е')
    intent=intent or local_intent(prompt,previous)
    if exact_target(prompt) or intent.action!='mix':return True
    if any(re.search(pattern,value) for pattern in ACTIONS.values()):return True
    if re.fullmatch(r'(?:а )?(?:еще|more|продолжай|keep going|another one)[.!? ]*',value):return True
    if intent.mode=='lookup' and intent.query:
        if re.match(r'^(?:найди|ищи|find|search for)\s',value):return True
        # Direct names stay fast. Lowercase descriptive sentences, including
        # two-word wishes such as "дождливый вечер", need semantic parsing.
        words=re.findall(r"[\w'-]+",intent.query)
        literal=re.sub(REQUEST_PREFIX,'',wish_text(prompt),flags=re.I)
        literal=re.sub(r'^(?:(?:музык[ауи]|песни|песен|треки|треков|music by|songs by|tracks by)\s+)+','',literal,flags=re.I).strip()
        if literal.casefold()==intent.query.casefold() and 0<len(words)<=6 and (all(w[:1].isupper() or w.casefold() in ('the','of','and') for w in words)
                or len(words)==1 and re.fullmatch(r'[a-zA-Z][a-zA-Z0-9-]*',intent.query)):
            return True
    if previous and previous.search:return False
    if intent.artists:
        for artist in intent.artists:
            if any(re.search(p,artist,re.I) for p in (*MOOD_WORDS.values(),*GENRES.values())):return False
            name_words=re.findall(r"[\w'-]+",artist)
            if not name_words or not (all(w[:1].isupper() or w.casefold() in ('the','of','and') for w in name_words)
                    or len(name_words)==1 and re.fullmatch(r'[a-zA-Z][a-zA-Z0-9-]*',artist)):
                return False
            value=re.sub(re.escape(artist.casefold()),' ',value)
    common=r'^(?:я|мне|меня|хочу|хочется|нужно|надо|бы|пожалуйста|можно|только|ну|а|но|и|так|да|давай|сделай|подбери|собери|включи|поставь|найди|послушать|слушать|музык\w*|песн\w*|трек\w*|немного|чуть|более|менее|очень|побольше|поменьше|больше|меньше|теперь|еще|какую|какой|что|чтобы|нибудь|то|либо|какая|какие|чего|настроени\w*|подн\w*|как|в|на|для|с|без|не|кроме|вокал\w*|слов|голос\w*|моем|моим|вкусе|похож\w*|стиле|любим\w*|знаком\w*|it|i|want|would|like|to|please|music|songs|tracks|something|anything|a|bit|more|less|make|the|me|my|taste|for|with|without|no|not|vocals|lyrics|instrumental|similar|play|find|some|new|familiar|favorites|favourites)$'
    patterns=(*MOOD_WORDS.values(),*GENRES.values())
    for pattern in patterns:value=re.sub(r'\w*(?:'+pattern+r')\w*',' ',value)
    return all(re.fullmatch(common,word) or any(re.search(pattern,word) for pattern in patterns)
               for word in re.findall(r'\w+',value))


def artist_key(value):
    value=re.sub(r'[^\w]+',' ',str(value).casefold()).strip()
    value=re.sub(r'^the\s+','',value)
    return {'битлз':'beatles','битлс':'beatles','битлы':'beatles'}.get(value,value)


def same_artist(actual,requested):
    target=artist_key(requested)
    if not target:return False
    if artist_key(actual)==target:return True
    return any(artist_key(part)==target for part in re.split(r'\s*(?:,|&|feat\.?| featuring | with | and )\s*',str(actual),flags=re.I))
