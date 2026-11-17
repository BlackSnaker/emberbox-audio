"""Small, deterministic vocabulary for sound and context, shared by DJ routing.

These are catalogue search hints, not audio analysis or a list of invented
recordings. Uncovered descriptions still go to the optional local model.
"""
import re

# pattern, search vocabulary, localized label. Whole phrases carry more meaning
# than scenery nouns alone ("rain" should not become a literal track search).
SOUNDS=(
    (r'на русском|русскоязычн\w*|русск\w*', 'russian', 'На русском'),
    (r'на французском|французск\w*', 'french', 'Французское звучание'),
    (r'британск\w*', 'british', 'Британская сцена'),
    (r'на японском|японск\w*', 'japanese', 'Японская сцена'),
    (r'девяност\w*|90[ -]?(?:е|х)|90s', '90s', 'Девяностые'),
    (r'восьмидесят\w*|80[ -]?(?:е|х)|80s', '80s', 'Восьмидесятые'),
    (r'нулев\w*|2000[ -]?(?:е|х|s)', '2000s', 'Нулевые'),
    (r'стар\w*\s+(?:джазов\w*\s+)?бар\w*', 'vintage jazz lounge', 'Винтажный джазовый бар'),
    (r'т[её]пл\w*|уют\w*|лампов\w*|потеплее|теплее|warm(?:er)?|coz(?:y|ier)|cosy', 'warm mellow', 'Тёплое звучание'),
    (r'винил\w*|винтаж\w*|ретро|стар\w* радио|vintage|vinyl|retro', 'vintage soul', 'Винтажное тепло'),
    (r'дожд\w*|rainy|rain', 'rainy mellow', 'Под шум дождя'),
    (r'ночн\w* (?:дорог\w*|поезд\w*|трасс\w*)|за рул[её]м|night driv(?:e|ing)|night road', 'night drive', 'Ночная дорога'),
    (r'парить|парю|невесом\w*|космос\w*|космическ\w*|воздушн\w*|ethereal|weightless|floating|spacey', 'ethereal ambient', 'Невесомое звучание'),
    (r'мураш\w*|до сл[её]з|пронзительн\w*|goosebumps|moving music', 'emotional cinematic', 'До мурашек'),
    (r'нуар\w*|noir', 'noir jazz', 'Атмосфера нуара'),
    (r'мрачн\w*|темн\w*|т[её]мн\w*|потемнее|dark(?:er)?|brooding', 'dark moody', 'Тёмные оттенки'),
    (r'светл\w*|посветлее|солнечн\w*|bright(?:er)?|sunny', 'bright uplifting', 'Солнечные ноты'),
    (r'ностальг\w*|как в детстве|из детства|nostalg\w*', 'nostalgic classics', 'Знакомые чувства'),
    (r'мечтательн\w*|будто во сне|dreamy|dreamlike', 'dreamy', 'Мечтательное звучание'),
    (r'кинематограф\w*|как в кино|саундтрек\w*|cinematic|soundtrack', 'cinematic', 'Как в кино'),
    (r'мягк\w*|помягче|нежн\w*|gentle|soft', 'gentle mellow', 'Мягкие оттенки'),
    (r'без агрессии|неагрессивн\w*|без тяжести|non aggressive', 'mellow', 'Без резкости'),
    (r'грув\w*|качало|groov\w*', 'groove', 'Больше грува'),
    (r'гитар\w*|guitars?', 'guitar', 'Гитарное звучание'),
    (r'пианино|фортепиан\w*|piano', 'piano', 'Фортепиано'),
    (r'на прогулк\w*|для прогулк\w*|walking', 'walking mellow', 'На прогулку'),
    (r'для готовки|пока готовлю|cooking', 'feel good', 'На кухонной волне'),
    (r'не отвлек\w*|фон\w* для (?:работ\w*|чтени\w*)|background for (?:work|reading)', 'focus ambient', 'Пространство для мыслей'),
    (r'после (?:долгого|тяж[её]лого|трудного) дня|устал\w*|снять напряжение|after a long day', 'chill mellow', 'Меньше спешки'),
    (r'прыгать|прыгал\w*|jump\w*|разогнат\w*', 'energetic dance', 'Больше движения'),
    (r'летн\w*|summer', 'summer feel good', 'Летнее настроение'),
    (r'утренн\w*|на утро|morning', 'morning mellow', 'Утренние ноты'),
)

FILLER=re.compile(r'\b(?:я|мне|меня|нам|у|хочу|хочется|хотелось|нужно|надо|бы|пусть|чтоб|чтобы|'
    r'можно|пожалуйста|давай|дай|включи|поставь|подбери|собери|сделай|что|чего|какой|какую|какие|'
    r'нибудь|то|либо|музык\w*|песн\w*|трек\w*|звучани\w*|немного|чуть|побольше|поменьше|'
    r'больше|меньше|очень|прям|как|будто|словно|для|под|на|в|во|с|со|без|не|и|но|а|теперь|'
    r'вечер\w*|вечером|дн[её]м|утром|ночью|настроени\w*|атмосфер\w*|при|этом|такое|такой|такая|'
    r'от|до|чего|комнат\w*|отдохнуть|слушать|послушать|послушаем|помоги|мне|быть|сидеть|оказаться|'
    r'жанр\w*|стил\w*|из|год\w*|'
    r'главн\w*|геро[йяе]\w*|фильм\w*|'
    r'i|want|would|like|some|something|anything|music|songs|tracks|please|a|the|to|for|of|'
    r'and|but|with|without|no|not|more|less|bit|little|make|it|in|on|my|me|genre|style|evening|tonight)\b',re.I)


def describe(value):
    """Return covered sound keywords and the unrecognized part of a wish."""
    rest=value;words=[];labels=[]
    for pattern,query,label in SOUNDS:
        pattern=r'(?<!\w)(?:'+pattern+r')(?!\w)'
        if re.search(pattern,rest,re.I):
            words.extend(query.split());labels.append(label)
            rest=re.sub(pattern,' ',rest,flags=re.I)
    rest=FILLER.sub(' ',rest)
    rest=re.sub(r'[^\w]+',' ',rest).strip()
    return tuple(dict.fromkeys(words)),tuple(labels),rest


def explicit_name(value):
    """Explicit entity markers override genre/mood words inside real names."""
    match=re.search(r'\b(?:групп[ауы]|исполнител[ья]|исполнитель|артист[а]?|band|artist|songs by|tracks by|music by)\s+[«"“]?(.+)',value,re.I)
    kind='artist'
    if not match:
        match=re.search(r'\b(?:трек|песню|композицию|song|track)\s+[«"“]?(.+)',value,re.I)
        kind='track'
    if not match:return None
    name=re.split(r'[,;]|\s+(?:но|только|but|without|для)\s+',match[1],maxsplit=1,flags=re.I)[0].strip(' .!?«»"“”')
    if not name or len(name)>100:return None
    # "песню для сна" and "трек повеселее" are wishes, not named titles.
    if kind=='track' and re.match(r'^(?:для|под|без|что|каку\w*|поспокой\w*|повесел\w*|погруст\w*|пободр\w*|поэнерг\w*|расслаб\w*|спокой\w*|весел\w*|груст\w*|бодр\w*|with|for|to|something)\b',name,re.I):return None
    qualifier=value[:match.start()]+' '+value[match.start(1)+len(name):]
    return kind,name,qualifier


OPPOSITES={
    'relax':r'energetic|energy|workout|motivation|fast|aggressive|hardcore|heavy|party',
    'focus':r'workout|aggressive|party',
    'happy':r'sad|melanchol\w*|moody|dark|brooding',
    'energy':r'sleep|calm|slow|relax\w*|chill',
    'party':r'sleep|calm|slow',
    'melancholy':r'happy|cheerful|upbeat|uplift\w*|bright|sunny|feel good',
}


def search_words(query,mood='any',avoid=()):
    """Drop contradicted descriptors instead of growing incompatible queries."""
    if mood in OPPOSITES:query=re.sub(r'\b(?:'+OPPOSITES[mood]+r')\b',' ',query,flags=re.I)
    for word in avoid:query=re.sub(r'(?<!\w)'+re.escape(word)+r'(?!\w)',' ',query,flags=re.I)
    return ' '.join(dict.fromkeys(query.split()))[:100].strip()
