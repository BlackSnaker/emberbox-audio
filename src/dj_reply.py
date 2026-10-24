"""Ember's replies describe the actual requested scope and returned recordings."""
from source_picker import text

MOODS={
 'relax':('A gentler set','Спокойное звучание'),'focus':('A set for concentration','Музыка для сосредоточенности'),
 'energy':('More energy in this set','Больше энергии в этом сете'),'party':('A dance set','Танцевальный сет'),
 'melancholy':('A reflective set','Музыка под задумчивое настроение'),
 'discover':('New names for this set','Новые имена в этом сете')}


def summary(intent):
    if intent.mode=='artist' and intent.artists:return text('Artist only: ','Только исполнитель: ')+', '.join(intent.artists)
    if intent.mode=='lookup':return text('Exact search: ','Точный поиск: ')+intent.query
    parts=[]
    if intent.mode=='similar' and intent.artists:parts.append(text('Music like ','Музыка в духе ')+', '.join(intent.artists))
    elif intent.mood in MOODS:parts.append(text(*MOODS[intent.mood]))
    if intent.genres:parts.append(', '.join(intent.genres))
    if intent.instrumental is True:parts.append(text('without vocals','без вокала'))
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
