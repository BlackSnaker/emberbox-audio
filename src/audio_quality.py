"""Honest stream badges: decoder evidence is separate from catalogue variants."""
from source_picker import text

CODECS={'aac':'AAC','opus':'Opus','vorbis':'Vorbis','mp3':'MP3','flac':'FLAC','alac':'ALAC',
        'pcm':'PCM','ac3':'Dolby Digital','eac3':'Dolby Digital Plus'}
FORMATS={'dolby-atmos':'Dolby Atmos','dolby-audio':'Dolby Audio',
         'hi-res-lossless':'Hi‑Res Lossless','lossless':'Lossless','lossy-stereo':text('Stereo','Стерео')}


def bounded(value,low,high):
    try:
        value=float(value)
        return value if low<=value<=high else 0
    except (ValueError,TypeError,OverflowError):return 0


def describe(state):
    """Only verified decoder/mpv fields may describe the playing format."""
    value=state.get('audioQuality')
    value=value if isinstance(value,dict) and value.get('evidence') in ('decoder','mpv') else {}
    codec=str(value.get('codec','')).lower()
    rate=bounded(value.get('sampleRate'),8000,768000)
    channels=int(bounded(value.get('channels'),1,32))
    bitrate=bounded(value.get('bitrate'),1000,100_000_000)
    depth=int(bounded(value.get('bitDepth'),1,64))
    known=codec in CODECS
    lossless=known and codec in ('flac','alac','pcm')
    name=(('Hi‑Res Lossless' if rate>48000 else 'Lossless') if lossless else CODECS.get(codec,''))
    # Multichannel and E-AC-3 alone do not confirm Dolby Atmos/JOC.
    if codec=='eac3' and value.get('variant')=='dolby-atmos' and value.get('evidence') in ('decoder','mpv'):
        name='Dolby Atmos'
    details=[CODECS[codec]] if known else []
    if known and depth and lossless:details.append(f'{depth} '+text('bit','бит'))
    if known and rate:
        frequency=f'{rate/1000:g}'.replace('.',text('.',','))
        details.append(frequency+' '+text('kHz','кГц'))
    if known and channels:
        details.append(text('Headphones · binaural PCM, 2 ch','Наушники · бинауральный PCM, 2 канала') if name=='Dolby Atmos' and value.get('renderer')=='openjoc-binaural'
            else text('Speaker pair · object PCM, 2 ch','Стереопара · объектный PCM, 2 канала') if name=='Dolby Atmos' and value.get('renderer')=='openjoc-speakers'
            else text('Stereo','Стерео') if channels==2 else text('Mono','Моно') if channels==1 else f'{channels} '+text('channels','каналов'))
    output_rate=bounded(value.get('outputSampleRate'),8000,768000)
    if known and output_rate and output_rate!=rate:details.append(text('Output','Выход')+': '+f'{output_rate/1000:g} '+text('kHz','кГц'))
    if known and bitrate:details.append('≈ '+f'{bitrate/1000:.0f}'+' '+text('kbps','кбит/с'))
    available=state.get('availableFormats')
    available=[FORMATS[k] for k in FORMATS if k in available] if isinstance(available,list) else []
    badge=name or text('Quality','Качество')
    if known and rate and not lossless:badge+=' · '+f'{rate/1000:g}'.replace('.',text('.',','))
    preference=state.get('qualityPreference')
    preference=preference if isinstance(preference,dict) else {}
    policy=''
    if preference.get('mode')=='maximum':
        policy=(text('Maximum supported quality requested.','Запрошено максимальное доступное качество.') if preference.get('applied') is True
            else text('The source needs an active subscription for this setting.','Для этой настройки нужна активная подписка источника.') if preference.get('reason')=='subscription'
            else text('Automatic quality selection is unavailable in this connection.','Автовыбор качества недоступен в этом подключении.'))
    elif preference.get('mode')=='external':
        policy=text('Choose the highest quality in the source app settings.','Выбери максимальное качество в настройках приложения-источника.')
    spatial=state.get('spatial') if isinstance(state.get('spatial'),dict) else {}
    scene=spatial.get('scene') or {}
    if known and scene.get('bluetooth'):
        transport='Bluetooth'+(' · '+str(scene.get('codec')).upper().replace('_',' ') if scene.get('codec') else '')
        details.append(transport)
    if spatial.get('enabled') and spatial.get('phase')=='preparing':
        badge=text('Preparing audio…','Готовим звук…') if spatial.get('losslessAvailable') else text('Preparing Atmos…','Готовим Atmos…');known=False;name=''
        details=[text('Preparing the best available stream','Подготовка лучшего доступного потока')]
    elif spatial.get('enabled') and spatial.get('error'):
        reason=(text('Apple device limit reached.','Достигнут лимит устройств Apple.') if spatial['error']=='DEVICE_LIMIT'
            else text('Reconnect Apple Lossless in player settings.','Переподключи Apple Lossless в настройках плеера.') if spatial['error']=='SPATIAL_FAIRPLAY_SIGN_IN_REQUIRED'
            else text('Native playback is unavailable for this attempt.','Нативное воспроизведение в этой попытке недоступно.'))
        policy=reason+' '+text('Standard playback restored.','Восстановлено обычное воспроизведение.')
    return {'badge':badge,'known':known,'name':name,'details':' · '.join(details),'available':available,'policy':policy}


def current(host):
    """Read cached state only: no IPC, socket calls, network or audio queries."""
    source=getattr(host,'source','')
    if source=='spotify' and getattr(host,'spotify_mode','')=='native':
        return describe(getattr(getattr(host,'spotify_web',None),'state',{}) or {})
    if source=='apple-music' and getattr(host,'apple_mode','')=='native':
        return describe(getattr(getattr(host,'apple_web',None),'state',{}) or {})
    if source=='yandex-music':
        return describe(getattr(getattr(host,'yandex_web',None),'state',{}) or {})
    if source=='youtube' and getattr(host,'youtube_mode','')=='native':
        audio=getattr(host,'youtube',None)
        return describe({'audioQuality':getattr(audio,'quality',{}) if getattr(audio,'loaded',False) else {},
                         'qualityPreference':{'mode':'maximum','applied':True}})
    # MPRIS and the optional browser companion do not report decoded quality.
    return describe({'qualityPreference':{'mode':'external'}})


def has_track(host):
    """A pending duration must not hide quality for an already selected song."""
    if getattr(host,'length',0) or getattr(host,'playing',False):return True
    source=getattr(host,'source','')
    if source=='spotify' and getattr(host,'spotify_mode','')=='native':
        state=getattr(getattr(host,'spotify_web',None),'state',{}) or {}
    elif source=='apple-music' and getattr(host,'apple_mode','')=='native':
        state=getattr(getattr(host,'apple_web',None),'state',{}) or {}
    elif source=='yandex-music':
        state=getattr(getattr(host,'yandex_web',None),'state',{}) or {}
    elif source=='youtube' and getattr(host,'youtube_mode','')=='native':
        audio=getattr(host,'youtube',None)
        return bool(getattr(audio,'current',None) or getattr(audio,'loaded',False))
    else:
        state=getattr(getattr(host,'session',None),'metadata',{}) or {}
        return bool(state.get('xesam:title'))
    return bool(state.get('title') or str(state.get('id') or '') not in ('','-1'))
