"""A source-aware personal DJ shared by the room and its existing music queue."""
from concurrent.futures import ThreadPoolExecutor
import threading,time
from dataclasses import replace
from gi.repository import GLib
from paths import CONFIG_DIR
from source_picker import text,RU
from music_library import snapshot,NAMES
from dj_intent import Intent
from dj_reply import reply,summary
from dj_memory import ListeningMemory
from dj_brain import LocalBrain
from dj_catalog import DJCatalog,rank
from dj_setup import ready,prepare,ROOT
from dj_voice import DJVoice

MOOD_LABEL={
 'any':('Your own wavelength','На твоей частоте'),'relax':('On a softer frequency','На мягких частотах'),
 'focus':('Room to concentrate','Пространство для мыслей'),'energy':('Sparks in every beat','Искры в каждом такте'),
 'party':('Where rhythm lives','Там, где живёт ритм'),'melancholy':('A feeling between the notes','Чувства между нотами'),
 'discover':('Somewhere you have not been','Знакомые чувства. Новые имена.')}


class DJService:
    def __init__(self,music):
        self.music=music;self.host=music.host
        self.memory=ListeningMemory(CONFIG_DIR/'dj-preferences.json')
        if not self.memory.path.exists():self.memory.settings['language']='ru' if RU else 'en'
        self.brain=LocalBrain();self.catalog=DJCatalog(music)
        self.voice=DJVoice(self.host,self.voice_event,lambda value:self.ask(value))
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='ember-dj')
        self.setup_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='ember-dj-setup')
        self.save_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='ember-dj-memory')
        self.listeners=[];self.closed=False;self.generation=0;self.cancelled=threading.Event()
        self.source=self.host.source;self.intents={};self.items=[];self.prompt='';self.partial=''
        self.phase='welcome';self.error='';self.intro='';self.understood='';self.engine='';self.models=[];self.probed=False
        self.busy=False;self.session=False;self.played=set();self.refill_after=0.;self.refilling=False
        self.setup_kind='';self.setup_phase='';self.setup_fraction=0.;self.setup_stop=threading.Event()
        self.save_busy=False;self.last_save=0.;self.last_track=''
        self.timer=GLib.timeout_add(500,self.poll)

    def subscribe(self,callback):
        self.listeners.append(callback)
        return lambda:self.listeners.remove(callback) if callback in self.listeners else None

    def changed(self):
        if not self.closed:
            for callback in tuple(self.listeners):callback()

    @property
    def language(self):return 'ru' if self.memory.settings.get('language')=='ru' else 'en'

    def activate(self):
        self.memory.settings['enabled']=True;self.memory.dirty=True
        if not self.probed:
            self.probed=True;future=self.pool.submit(self.brain.models)
            future.add_done_callback(lambda result:GLib.idle_add(self.probe_done,result,priority=GLib.PRIORITY_DEFAULT))
        self.changed()

    def probe_done(self,future):
        if not self.closed:
            try:self.models=future.result()
            except Exception:self.models=[]
            self.changed()
        return False

    def option(self,key,value):
        if key not in ('voice','language','ai','model'):return
        if key=='language':self.voice.cancel()
        self.memory.settings[key]=value;self.memory.dirty=True;self.changed()

    def cancel(self):
        self.generation+=1;self.cancelled.set();self.cancelled=threading.Event()
        self.busy=self.refilling=False;self.voice.cancel()

    def ask(self,prompt):
        prompt=str(prompt).strip()[:500]
        if not prompt or self.closed:return
        if self.source!=self.host.source:self.switch_source()
        self.cancel();self.prompt=prompt;self.partial='';self.error='';self.intro='';self.understood='';self.phase='understand';self.busy=True
        source=self.host.source;generation=self.generation;cancelled=self.cancelled
        previous=self.intents.get(source)
        settings=dict(self.memory.settings)
        alive=lambda:not self.closed and not cancelled.is_set() and source==self.host.source
        def progress(phase):GLib.idle_add(self.progress,generation,phase,priority=GLib.PRIORITY_DEFAULT)
        def build():
            intent,engine=self.brain.interpret(prompt,previous,settings.get('ai',False),settings.get('model','qwen2.5:1.5b'),alive)
            if not alive():raise InterruptedError('cancelled')
            if intent.action!='mix':return intent,engine,[],[]
            affinity=self.memory.artist_affinity(source)
            values,recent,warnings=self.catalog.collect(source,intent,affinity,alive,progress)
            if not alive():raise InterruptedError('cancelled')
            resolved=next((v.get('_requested_artist') for v in values if v.get('_requested_artist')),None)
            if resolved:intent=replace(intent,artists=(resolved,),mode='artist')
            self.memory.import_recent(source,recent)
            selected=rank(values,source,intent,self.memory.profile(source),self.memory.artist_affinity(source),
                          seed=str(generation)+prompt)
            return intent,engine,selected,warnings
        future=self.pool.submit(build)
        future.add_done_callback(lambda result:GLib.idle_add(self.built,generation,source,result,priority=GLib.PRIORITY_DEFAULT))
        self.changed()

    def progress(self,generation,phase):
        if generation==self.generation and not self.closed:self.phase=phase;self.changed()
        return False

    def built(self,generation,source,future):
        if self.closed or generation!=self.generation or source!=self.host.source:return False
        self.busy=False
        try:intent,engine,items,warnings=future.result()
        except InterruptedError:return False
        except Exception:
            self.phase='error';self.error=text('The source did not return a mix. Check its connection and try again.',
                'Источник не вернул подборку. Проверь подключение и попробуй ещё раз.');self.changed();return False
        self.engine=engine
        if intent.action!='mix':self.command(intent.action);return False
        self.intents[source]=intent;self.understood=summary(intent)
        if not items:
            self.phase='empty'
            self.error=text('No matching playable tracks were found. Try a different wish or connect your library.',
                'Подходящие доступные треки не нашлись. Попробуй другое пожелание или подключи медиатеку.')
            if 'pending' in warnings:self.error=text('The source is still responding. Results are being cached; try your wish again shortly.',
                'Источник ещё отвечает. Сохраняю результаты в кэш — повтори пожелание чуть позже.')
            elif intent.instrumental is True:self.error=text('No clearly labelled instrumental versions were found. Try an artist or genre.',
                'Не нашлись явно обозначенные инструментальные версии. Попробуй указать исполнителя или жанр.')
            self.changed();return False
        if not self.music.play_dj(items):
            self.phase='error';self.error=text('The queue is full. Free a little space for the DJ.',
                'Очередь заполнена. Освободи немного места для DJ.');self.changed();return False
        self.items=items;self.played={v['uri'] for v in items};self.source=source;self.session=True
        self.refill_after=time.monotonic()+15;self.phase='playing'
        self.intro=reply(intent,items,NAMES[source])
        if self.memory.settings.get('voice') and ready('voice',self.language):self.voice.launch('speak',self.language,self.intro)
        self.changed();return False

    def state(self):
        value=snapshot(self.host);source=self.host.source
        if not value.get('uri') and value.get('id'):
            ident=str(value['id'])
            prefix={'spotify':'spotify:track:','apple-music':'apple:'+('library-songs:' if ident.startswith('i.') else 'songs:'),
                    'youtube':'youtube:','yandex-music':'yandex:track:'}[source]
            value['uri']=prefix+ident
        return value

    def feedback(self,vote):
        current=self.state()
        if current.get('valid'):
            self.memory.record(self.host.source,current,'like' if vote>0 else 'dislike')
            self.intro=text('Remembered for your Ember DJ mixes.','Запомнила для твоих подборок Ember DJ.')
            if vote<0:self.next()
            self.changed()

    def next(self):
        current=self.state()
        if current.get('valid'):self.memory.record(self.host.source,current,'skip')
        if self.music.book.active==self.host.source:self.music.step(1)
        else:self.host.on_action(None,'next')

    def command(self,action):
        self.phase='playing' if self.session else 'welcome'
        if action in ('like','dislike'):self.feedback(1 if action=='like' else -1)
        elif action=='next':self.next()
        elif action=='pause':
            if self.host.playing:self.host.on_action(None,'toggle')
        elif action=='resume':
            if not self.host.playing:self.host.on_action(None,'toggle')
        self.changed()

    def stop(self):
        self.cancel();self.session=False;self.phase='welcome'
        self.music.clear_dj(self.source);self.changed()

    def switch_source(self):
        previous=self.source;self.cancel();self.session=False;self.items=[];self.intro=''
        self.source=self.host.source;self.phase='welcome';self.music.clear_dj(previous);self.changed()

    def play_item(self,item):
        source=self.host.source
        for index,value in enumerate(self.music.book.queues[source]):
            if value.get('uri')==item.get('uri') and value.get('origin')=='dj':
                self.music.start(index);self.session=True;self.source=source;self.changed();return
        self.music.play_dj([item]);self.session=True;self.source=source;self.changed()

    def forget(self):
        self.memory.clear();self.catalog.cache.clear();self.intro=text('A fresh start. Tell me what you would like to hear.',
            'Начнём с чистого листа. Расскажи, что хочется послушать.');self.changed()

    def poll(self):
        if self.closed:return False
        now=time.monotonic()
        if not self.busy and self.brain.process and now-self.brain.last_use>30:self.brain.park()
        if self.source!=self.host.source:
            self.switch_source()
        if self.memory.settings.get('enabled'):
            try:self.memory.observe(self.host.source,self.state(),now)
            except (AttributeError,ValueError,KeyError):pass
        if self.memory.dirty and not self.save_busy and now-self.last_save>3:
            self.save_busy=True;self.last_save=now;future=self.save_pool.submit(self.memory.save)
            future.add_done_callback(lambda result:GLib.idle_add(self.saved,result))
        current=self.music.book.current(self.source)
        track_key=(self.music.book.active,current.get('uri') if current else '',self.host.playing)
        if track_key!=self.last_track:self.last_track=track_key;self.changed()
        if self.session and not self.busy:
            current=self.music.book.current(self.source)
            if self.music.book.active!=self.source or current and current.get('origin')!='dj':
                self.session=False;self.music.clear_dj(self.source);self.changed()
            elif current:
                pending=[v for _,v in self.music.book.upcoming(self.source) if v.get('origin')=='dj']
                if len(pending)<=3 and now>=self.refill_after:self.refill()
        return True

    def saved(self,future):
        self.save_busy=False
        try:future.result()
        except OSError:pass
        return False

    def refill(self):
        intent=self.intents.get(self.source)
        if intent is None:return
        source=self.source;generation=self.generation;cancelled=self.cancelled;exclude=set(self.played)
        self.busy=self.refilling=True;self.refill_after=time.monotonic()+60
        alive=lambda:not self.closed and not cancelled.is_set() and source==self.host.source
        def build():
            affinity=self.memory.artist_affinity(source)
            values,_,_=self.catalog.collect(source,intent,affinity,alive)
            selected=rank(values,source,intent,self.memory.profile(source),affinity,exclude,seed=str(time.time()))
            if not selected and intent.mode=='artist':
                current=self.music.book.current(source) or {}
                selected=rank(values,source,intent,self.memory.profile(source),affinity,
                    {current.get('uri','')},seed=str(time.time()))
            return selected
        future=self.pool.submit(build)
        def done(result):
            if self.closed or generation!=self.generation or source!=self.host.source:return False
            self.busy=self.refilling=False
            try:items=result.result()
            except Exception:items=[]
            if items:
                self.music.extend_dj(items,before_pending=intent.mode=='artist');self.played.update(v['uri'] for v in items)
                self.items=(self.items+items)[-40:]
            self.changed();return False
        future.add_done_callback(lambda result:GLib.idle_add(done,result,priority=GLib.PRIORITY_DEFAULT))
        self.changed()

    def voice_event(self,event,data):
        if event=='partial':self.partial=data.get('text','')
        elif event=='voice-error':self.error=text('Could not hear that. Try the microphone again or type your wish.',
            'Не удалось расслышать. Попробуй ещё раз или напиши пожелание.')
        self.changed()

    def microphone(self):
        if self.voice.mode=='listen':
            if self.voice.phase=='preparing-voice':self.voice.cancel();self.changed()
            else:self.voice.stop_listening()
            return
        if not ready('voice',self.language):self.setup('voice');return
        self.partial='';self.error='';self.voice.launch('listen',self.language);self.changed()

    def setup(self,kind):
        if self.setup_kind:return
        self.voice.cancel();self.setup_kind=kind;self.setup_phase='download';self.setup_fraction=0.;self.error=''
        self.setup_stop=threading.Event();language=self.language
        def progress(phase,fraction):
            GLib.idle_add(self.setup_progress,phase,fraction,priority=GLib.PRIORITY_DEFAULT)
        def install():
            try:return prepare(kind,language,progress,self.setup_stop)
            except InterruptedError:raise
            except Exception as error:
                try:
                    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
                    log=ROOT/'setup.log'
                    with log.open('a') as stream:stream.write('\n'+type(error).__name__+': '+str(error)[:1000]+'\n')
                    log.chmod(0o600)
                except OSError:pass
                raise
        future=self.setup_pool.submit(install)
        future.add_done_callback(lambda result:GLib.idle_add(self.setup_done,result,priority=GLib.PRIORITY_DEFAULT))
        self.changed()

    def setup_progress(self,phase,fraction):
        if not self.closed and self.setup_kind:self.setup_phase=phase;self.setup_fraction=fraction;self.changed()
        return False

    def setup_done(self,future):
        kind=self.setup_kind;self.setup_kind=''
        try:
            future.result();self.error=''
            self.intro=text('Voice is ready. Press the microphone to say your wish.','Голос готов. Нажми микрофон и скажи своё пожелание.') if kind=='voice' else text('Local AI is ready. Tell me what you would like to hear.','Локальный ИИ готов. Расскажи, что хочется послушать.')
        except InterruptedError:pass
        except Exception:self.error=text('Could not prepare the DJ. Check the connection and retry; details are in the private setup log.',
            'Не удалось подготовить DJ. Проверь сеть и повтори; подробности — в приватном журнале установки.')
        self.changed();return False

    def close(self):
        if self.closed:return
        self.closed=True;self.cancel();self.setup_stop.set();self.voice.close();self.brain.close();self.catalog.close()
        GLib.source_remove(self.timer)
        try:self.memory.save()
        except OSError:pass
        self.listeners.clear()
        for pool in (self.pool,self.setup_pool,self.save_pool):pool.shutdown(wait=False,cancel_futures=True)
