"""Ember's replies describe the actual requested scope and returned recordings."""
from source_picker import text
import hashlib

MOODS={
 'relax':('A gentler set','Спокойное звучание'),'focus':('A set for concentration','Музыка для сосредоточенности'),
 'energy':('More energy in this set','Больше энергии в этом сете'),'party':('A dance set','Танцевальный сет'),
 'happy':('A brighter, feel-good set','Позитивное звучание, повеселее'),'romance':('A romantic set','Романтическое настроение'),
 'melancholy':('A reflective set','Музыка под задумчивое настроение'),
 'discover':('New names for this set','Новые имена в этом сете')}


def summary(intent):
    parts=[]
    if intent.caption and intent.mode=='mix':parts.append(intent.caption)
    if intent.mode=='artist' and intent.artists:parts.append(text('Artist only: ','Только исполнитель: ')+', '.join(intent.artists))
    elif intent.mode=='lookup':parts.append(text('Exact search: ','Точный поиск: ')+intent.query)
    elif intent.mode=='theme':parts.append(text('A set for: ','Подборка: ')+intent.query)
    elif intent.mode=='similar' and intent.artists:parts.append(text('Music like ','Музыка в духе ')+', '.join(intent.artists))
    if not intent.caption and intent.mood in MOODS:parts.append(text(*MOODS[intent.mood]))
    genres=[g for g in intent.genres if not intent.caption or g not in intent.search.casefold()]
    if genres:parts.append(', '.join(genres))
    if intent.instrumental is True:parts.append(text('without vocals','без вокала'))
    elif intent.instrumental is False:parts.append(text('with vocals','с вокалом'))
    if intent.avoid:parts.append(text('excluding ','исключая ')+', '.join(intent.avoid))
    return ' · '.join(parts) or text('Personal music selection','Персональная подборка музыки')


def reply(intent,items,source):
    count=len(items);first=items[0] if items else {}
    song=' — '.join(str(first.get(k) or '') for k in ('artist','title')).strip(' —')
    if intent.mode=='artist' and intent.artists:
        name=', '.join(intent.artists)
        result=text(f'{name} only. I found {count} tracks in {source}.',f'Только {name}. Я нашла в {source} треков: {count}.')
    elif intent.mode=='lookup':
        result=text(f'I found {count} matching recordings for “{intent.query}” in {source}.',
                    f'По запросу «{intent.query}» я нашла в {source} совпадений: {count}.')
    elif intent.mode=='similar' and intent.artists:
        result=text(f'A mix around {", ".join(intent.artists)}: {count} tracks from {source}.',
                    f'Вокруг звучания {", ".join(intent.artists)} — треков в подборке: {count}. Источник — {source}.')
    else:
        direction=summary(intent)
        result=text(f'{direction}. I selected {count} tracks from {source}.',
                    f'{direction}. Я подобрала в {source} треков: {count}.')
    if song:result+=text(f' First up: {song}.',f' Первой прозвучит «{song}».')
    if intent.mode=='artist':result+=text(' No other artists will be added automatically.',
                                        ' Других исполнителей автоматически не добавляю.')
    return result


def spoken_reply(intent,items,language='ru'):
    """A short radio link; catalogue diagnostics stay in the written answer."""
    choose=lambda en,ru:ru if language=='ru' else en
    if intent.caption and intent.mode=='mix':
        import re
        if bool(re.search('[А-Яа-яЁё]',intent.caption))==(language=='ru'):
            return intent.caption.replace(' · ','. ').rstrip('.!?')+choose('. Your new set is ready.','. Я подобрала новый сет.')
    if intent.mode=='artist':
        name=intent.artists[0] if intent.artists else ''
        names={'the beatles':'Битлз','beatles':'Битлз','queen':'Куин','tame impala':'Тейм Импала',
               'daft punk':'Дафт Панк','michael jackson':'Майкл Джексон'}
        import re
        name=names.get(name.casefold(),name if re.fullmatch(r'[А-Яа-яЁё .-]{2,60}',name) else '')
        return choose('Only the artist you asked for. Your next set is ready.',
            ('Только '+name+'. ' if name else 'Только выбранный исполнитель. ')+
            ('Я подобрала песни повеселее.' if intent.mood=='happy' else 'Новая подборка уже звучит.'))
    if intent.mode=='lookup':return choose('Found your recording. Here it comes.','Я нашла нужную запись. Сейчас она зазвучит.')
    directions={
        'happy':(('A little more sunshine. Here is a brighter set.', 'Now for something happier. I picked a brighter sound.'),
                 ('Теперь побольше света и ритма. Я подобрала музыку повеселее.', 'Да, теперь повеселее. В новой подборке больше светлого настроения.')),
        'relax':(('A softer sound, with room between the notes.', 'A gentler set is ready. A little less rush, a little more space.'),
                 ('Теперь мягче и спокойнее. Я подобрала более нежное звучание.', 'В этой подборке чуть меньше спешки и больше пространства между нотами.')),
        'focus':(('A new set for concentration. Music to keep you company.', 'A quieter background for your thoughts. Your set is ready.'),
                 ('Музыка для твоих мыслей. Я подобрала спокойный фон для работы.', 'Немного музыки для сосредоточенности. Новая подборка уже звучит.')),
        'energy':(('A little more drive. Here is your next set.', 'More energy in the next few records. Here we go.'),
                  ('Теперь поживее. Я подобрала музыку с более энергичным настроением.', 'Больше движения и драйва. Новая подборка уже в эфире.')),
        'party':(('A new set with a little more rhythm.', 'There is a dance floor somewhere in these records.'),
                 ('Теперь побольше танцевального настроения. Я подобрала новый сет.', 'В этой подборке всё крутится вокруг ритма. Музыка уже звучит.')),
        'romance':(('A little warmth between the notes. This set is for that feeling.', 'A new set for a little closeness.'),
                   ('Немного тепла между нотами. Я подобрала музыку для этого настроения.', 'В новой подборке больше нежности. Музыка уже звучит.')),
        'melancholy':(('A few records for a reflective mood.', 'A little wistfulness in the next set. Here it comes.'),
                      ('Немного меланхолии между нотами. Я подобрала музыку под это настроение.', 'В этой подборке есть место задумчивости. Новый сет уже звучит.')),
        'discover':(('A different direction. Here is a new set to explore.', 'A new turn for your radio. Let us see where these records go.'),
                    ('Теперь другое направление. Я собрала новую подборку.', 'Новый поворот твоей волны. Я подобрала другое звучание.'))}
    if intent.mood in directions:
        en,ru=directions[intent.mood];variants=choose(en,ru)
        index=int(hashlib.sha256(str(items[0].get('uri','') if items else '').encode()).hexdigest()[:8],16)%len(variants)
        return variants[index]
    return choose('Your next musical chapter is ready. Here comes the first record.',
                  'Продолжение твоей музыкальной истории. Я подобрала песни для нового сета.')
