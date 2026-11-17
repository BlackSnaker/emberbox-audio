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
    'metal':r'метал(?:л(?:а|у|ом|е)?|лическ\w*)?(?![а-яё])|потяжелее|пожестче|\bmetal\b|heavier','ambient':r'эмбиент|амбиент|\bambient\b',
    'electronic':r'электрон|electronic','classical':r'классик|classical',
    'hip hop':r'хип.хоп|\bрэп\w*|hip.hop|\brap\b','pop':r'\bпоп(?:а|е|ом)?\b|\bpop\b',
    'soul':r'соул|\bsoul\b','funk':r'фанк|\bfunk\b','lofi':r'лоу.?фай|ло.?фай|lo.?fi',
    'acoustic':r'акустик|acoustic','folk':r'фолк|\bfolk\b','techno':r'техно|\btechno\b',
    'house':r'хаус|\bhouse\b','reggae':r'регги|reggae','r&b':r'ритм.энд.блюз|r\s*[&n]\s*b',
    'drum and bass':r'драм.?[эе]нд.?б[еэ]йс|драм.?н.?б[еэ]йс|drum (?:and|&) bass|d[&n]b',
    'synthwave':r'синтвейв|синтвей[фв]|synthwave','disco':r'диско|disco',
    'punk':r'панк|punk','country':r'кантри|country','trip hop':r'трип.?хоп|trip.hop',
    'shoegaze':r'шугейз|shoegaze','dream pop':r'дрим.?поп|dream.pop',
    'post rock':r'пост.?рок|post.rock','deep house':r'дип.?хаус|deep.house',
    'bossa nova':r'бос[ас]а.?нова|bossa.nova','swing':r'свинг|swing',
    'post punk':r'пост.?панк|post.punk'}
# Russian inflections are explicit too: a broad "рок\\w*" also eats Рокет.
GENRES.update({
    'indie':r'инди|indie', 'jazz':r'джаз(?:а|у|ом|е|ов\w*)?|jazz',
    'rock':r'рок(?:а|у|ом|е|ов\w*)?|rock',
    'ambient':r'[эа]мбиент(?:а|у|ом|е|н\w*)?|ambient',
    'electronic':r'электроник(?:а|у|и|ой|е)|электронн\w*|electronic',
    'classical':r'классик(?:а|у|и|ой|е)|классическ\w*|classical',
    'hip hop':r'хип.хоп(?:а|у|ом|е)?|рэп(?:а|у|ом|е)?|hip.hop|rap',
    'soul':r'соул(?:а|у|ом|е)?|soul', 'funk':r'фанк(?:а|у|ом|е|ов\w*)?|funk',
    'folk':r'фолк(?:а|у|ом|е|ов\w*)?|folk', 'techno':r'техно|techno',
    'acoustic':r'акустик(?:а|у|и|ой|е)|акустическ\w*|acoustic',
    'house':r'хаус(?:а|у|ом|е|ов\w*)?|house',
    'blues':r'блюз(?:а|у|ом|е|ов\w*)?|blues',
    'disco':r'диско|disco', 'punk':r'панк(?:а|у|ом|е|ов\w*)?|punk',
})
# Names such as Metallica, Jazztronik and Household are never genre evidence.
GENRES={key:r'(?<!\w)(?:'+pattern+r')(?!\w)' for key,pattern in GENRES.items()}
ACTIONS={
    'like':r'^(?:это )?(?:нравится|люблю это|классный трек|запомни это|like|love this)(?:[.! ]*)$',
    'dislike':r'^(?:это )?(?:не мо[её]|не нравится|не хочу это|dislike|not for me)(?:[.! ]*)$',
    'next':r'^(?:дальше|следующ(?:ий|ая|ее)|пропусти(?: трек)?|next|skip)(?:[.! ]*)$',
    'pause':r'^(?:пауза|останови(?: музыку)?|pause|stop music)(?:[.! ]*)$',
    'resume':r'^(?:продолжи(?: музыку)?|resume|continue music)(?:[.! ]*)$'}


def clean(value,limit=80):return re.sub(r'\s+',' ',str(value or '')).strip()[:limit]


def mask_vocabulary(value):
    spans=[]
    for pattern in (*GENRES.values(),*MOOD_WORDS.values()):
        for match in re.finditer(pattern,value,re.I):
            start=match.start()-len(re.search(r'\w*$',value[:match.start()])[0])
            end=match.end()+len(re.match(r'\w*',value[match.end():])[0])
            spans.append((start,end))
    for start,end in sorted(spans,reverse=True):value=value[:start]+' '*(end-start)+value[end:]
    return value


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
    target_kind:str='auto'
    def data(self):return asdict(self)


def _basic_intent(prompt,previous=None):
    exact=exact_target(prompt)
    if exact:return Intent(query=exact,mode='lookup',target_kind='track')
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
    filler=r'\b(?:'+INDEFINITE+r'|музык\w*|песни|песен|песню|треки|треков|трек|немного|побольше|поменьше|чуть|еще|ещё|теперь|пожалуйста|сделай|давай|более|менее|очень|чуточку|лучше|хотелось|хочется|нужн\w*|надо|как|но|а|и|для|меня|мне|на|от|бы|в|же|они|их|этого|исполнителя|этой|группы|этом|духе|звучании|вкусе|моем|моём|something|anything|music|songs?|tracks?|a|bit|more|less|some|it|make|please|but|and|by|of|them|same|artist|to|for|me)\b'
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


def local_intent(prompt,previous=None):
    """Names are protected before extracting sound; qualifiers stay separate."""
    from dj_language import explicit_name,describe,search_words
    value=wish_text(prompt)
    exact=exact_target(prompt)
    if exact:return Intent(query=exact,mode='lookup',target_kind='track')
    named=explicit_name(value)
    if named:
        kind,name,qualifier=named
        detail=_basic_intent(qualifier)
        return replace(detail,query=name,mode='artist' if kind=='artist' else 'lookup',
            artists=(name,) if kind=='artist' else (),target_kind=kind,search='',caption='')
    similar=re.search(r'(?:как|в стиле|похож[а-я]* на|like|similar to)\s+(.{2,80}?)(?=,|\s+(?:но|только|без|but|without)\b|$)',value,re.I)
    if similar:
        name=similar[1].strip()
        genre_only=any(re.fullmatch(pattern,name,re.I) for pattern in GENRES.values())
        scene=bool(re.match(r'^(?:в|на|будто|словно|я)\b',name,re.I) or describe(name)[0])
        if not genre_only and not scene:
            # Mask the COMPLETE name before parsing qualifiers: the word
            # "punk" inside "daft punk" must not become a requested genre.
            qualifier=value[:similar.start()]+value[similar.end():]
            detail=_basic_intent(qualifier)
            return replace(detail,query=name,mode='similar',artists=(name,),target_kind='artist')
    literal=re.sub(REQUEST_PREFIX,'',value,flags=re.I).strip(' ,.!?')
    words=re.findall(r"[\w'-]+",literal)
    # "Pop Smoke" is a name even though its first word is also a genre.
    # A complete genre phrase such as "Indie Rock" remains a genre request.
    residue=literal
    residue=mask_vocabulary(residue)
    if (1<len(words)<=5 and residue.strip() and
            all(w[:1].isupper() or w.casefold() in ('the','of','and','a','van') for w in words) and
            not describe(literal)[0]):
        return Intent(query=literal,mode='lookup')
    result=_basic_intent(value,previous)
    if result.action!='mix':return result
    if result.mode=='similar':
        genre_only=any(re.fullmatch(pattern,result.query,re.I) for pattern in GENRES.values())
        if genre_only:result=replace(result,mode='mix',query='',artists=())
        elif not re.match(r'^(?:в|на|будто|словно|я)\b',result.query,re.I):return result
    # Atomic subgenres must not leave "post" / "deep" behind as a name.
    parents={'dream pop':'pop','post rock':'rock','deep house':'house','post punk':'punk'}
    genres=tuple(g for g in result.genres if g not in result.avoid and
        not any(child in result.genres and parent==g for child,parent in parents.items()))
    positive=re.sub(r'(?:\bбез\b|\bне хочу\b|\bне\b|\bкроме\b|\bno\b|\bnot\b|\bwithout\b)\s+[^,.;]+?(?=,|[.;]|\s+(?:но|а|but)\s+|$)', ' ',value,flags=re.I)
    rest=mask_vocabulary(positive)
    keywords,labels,uncovered=describe(rest)
    # A recognized, fully covered description can run without loading a model.
    # Never turn an uncovered name or sentence into a playlist keyword.
    if re.search(r'без (?:агрессии|тяжести)|неагрессивн|non aggressive',value,re.I):
        keywords=tuple(dict.fromkeys((*keywords,'mellow')))
        labels=(*labels,'Без резкости')
        result=replace(result,avoid=tuple(dict.fromkeys((*result.avoid,'aggressive'))))
    if not uncovered and (keywords or genres):
        from dj_semantics import follows,caption_for
        if previous and previous.mode in ('mix','theme') and follows(value):
            explicit_genres=any(re.search(pattern,positive,re.I) for pattern in GENRES.values())
            if not explicit_genres:genres=tuple(g for g in previous.genres if g not in result.avoid)
            result=replace(result,instrumental=result.instrumental if result.instrumental is not None else previous.instrumental)
        result=replace(result,genres=genres,query='',artists=(),mode='mix')
        if keywords:
            mood=result.mood
            if mood=='any':
                mood='focus' if 'focus' in keywords else 'energy' if 'energetic' in keywords else 'relax' if any(w in keywords for w in ('mellow','ambient')) else 'any'
            direction={'relax':'chill','focus':'focus','energy':'energetic','happy':'feel good',
                'party':'dance','romance':'romantic','melancholy':'melancholy','discover':'new music'}.get(mood,'')
            search=' '.join(dict.fromkeys((*genres,*keywords,direction)))
            if previous and previous.search:
                if follows(value) and (not genres or genres==previous.genres):
                    search=previous.search+' '+search
            search=search_words(search,mood,result.avoid)
            return replace(result,mood=mood,search=clean(search,80),caption=caption_for(search))
    result=replace(result,genres=genres)
    if result.search:
        from dj_semantics import caption_for
        search=search_words(result.search,result.mood,result.avoid)
        result=replace(result,search=search,caption=caption_for(search))
    if previous and result.mode==previous.mode and result.query==previous.query:
        result=replace(result,target_kind=previous.target_kind)
    return result



def quick_wish(prompt,previous=None,intent=None):
    """Only fully covered wishes bypass inference; length is not confidence."""
    value=wish_text(prompt).casefold().replace('ё','е')
    intent=intent or local_intent(prompt,previous)
    if exact_target(prompt) or intent.action!='mix':return True
    if intent.target_kind in ('artist','track'):return True
    if intent.avoid and intent.mode=='mix':
        from dj_language import describe
        if not describe(mask_vocabulary(wish_text(prompt)))[2]:return True
    if intent.genres and intent.mode=='mix' and not intent.search:
        from dj_language import describe
        rest=mask_vocabulary(wish_text(prompt))
        if not describe(rest)[2]:return True
    if intent.search and intent.mode=='mix':
        # Deterministic sound descriptions are deliberately bounded; a model
        # is still needed for descriptions with unrecognized words.
        from dj_language import describe
        rest=mask_vocabulary(wish_text(prompt))
        if describe(rest)[0] and not describe(rest)[2]:return True
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
                or len(words)==1 and re.fullmatch(r'[a-zA-Zа-яА-ЯёЁ][a-zA-Zа-яА-ЯёЁ0-9-]*',intent.query)):
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
