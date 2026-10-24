"""Ember DJ's warm radio desk: keyboard wishes, push-to-talk and real tracks."""
from gi.repository import Gtk,Pango
from source_picker import text
from listening_library import label,button,scroll,duration
from discovery_panel import clear
from music_library import NAMES
from dj_service import MOOD_LABEL
from dj_setup import ready
from dj_signal import DJSignal

CSS=b'''
.ember-stage .small-screen .stage-top-nav button.stage-tab { padding:7px 9px;font-size:10px; }
.dj-desk { background-image: linear-gradient(to bottom right,rgba(73,66,44,.75),rgba(26,35,28,.92));
  border: 1px solid rgba(244,219,162,.065); border-radius: 27px; padding: 22px 26px;
  box-shadow: inset 0 1px rgba(255,235,188,.06); }
.dj-frequency { color: #d4ac5b; font-size: 10px; letter-spacing: 2px; }
.dj-title { color: #fbf1c7; font-weight: bold; font-size: 48px; letter-spacing: -1px; }
.dj-reply { color: #d5c4a2; font-size: 13px; }
.dj-hint { color: #a89984; font-size: 11px; }
.dj-status { color: #d5b66b; font-size: 11px; }
.ember-stage button.dj-microphone, .ember-stage button.dj-microphone:hover,
.ember-stage button.dj-microphone:active, .ember-stage button.dj-microphone:focus {
  background:transparent;border:none;box-shadow:none;padding:0;min-width:0;min-height:0; }
.dj-on-air { color:#d6b56b;font-size:10px;letter-spacing:1px; }
.dj-station-note { color:#ad9e7e;font-size:10px;letter-spacing:1px; }
.dj-track-number { color:#b99a55;font-size:10px; }
.dj-flow flowboxchild { padding:0;outline:none; }
.ember-stage entry.dj-entry { background-image: linear-gradient(to bottom,#1c241e,#222a21);
  color:#fbf1c7; border:1px solid rgba(217,190,126,.12);border-radius:19px;padding:12px 17px;
  font-size:14px;box-shadow:inset 1px 2px 6px rgba(0,0,0,.2); }
.ember-stage entry.dj-entry:focus { border-color:rgba(239,187,77,.45); }
.ember-stage button.dj-send { border-radius:19px;padding:12px 19px; }
.ember-stage button.dj-preset { font-size:11px;padding:6px 12px; }
.dj-preferences { background:rgba(12,22,15,.28);border-radius:19px;padding:14px 17px; }
.dj-wish { color:#bbae8d;font-size:11px; }
.dj-track { background-image:linear-gradient(to right,rgba(44,53,39,.8),rgba(24,33,25,.72));
  border:1px solid rgba(234,216,168,.035);border-radius:17px;padding:7px 12px; }
.dj-track.dj-current { border-color:rgba(240,180,62,.27);background-color:rgba(118,86,31,.09); }
.dj-reason { color:#bfa873;font-size:10px; }
.dj-micro-level trough { min-height:3px; min-width:62px;background:#182019;border:none;border-radius:4px; }
.dj-micro-level progress { min-height:3px;background:#ecb54b;border-radius:4px; }
.ember-stage .small-screen .dj-desk { padding:13px 17px;border-radius:21px; }
.ember-stage .small-screen .dj-title { font-size:26px;letter-spacing:-.5px; }
.ember-stage .small-screen entry.dj-entry { font-size:12px;padding:9px 12px; }
.ember-stage .small-screen button.dj-send { font-size:11px;padding:9px 12px; }

.ember-stage .small-screen .dj-reply { font-size:11px; }
.ember-stage .small-screen .dj-preset { padding:5px 8px;font-size:10px; }
'''

PHASES={'welcome':('Mood, a style, a few words. Then music.','Настроение, стиль, пара слов. Дальше — музыка.'),
 'understand':('Listening to your wish…','Понимаю твоё пожелание…'),
 'personal':('Tuning in to your taste…','Настраиваюсь на твои вкусы…'),
 'catalogue':('Finding the right records…','Подбираю подходящие записи…'),
 'playing':('Your wavelength is on air','Твоя волна в эфире'),
 'empty':('Let us try a different direction','Попробуем другое направление'),
 'error':('A small pause. We can try again.','Небольшая пауза. Можно попробовать ещё раз.')}
REASONS={'personal':('From your personal picks','Из твоих личных подборок'),
 'artist':('An artist you return to','Исполнитель, к которому ты возвращаешься'),
 'catalogue':('A catalogue discovery','Открытие из каталога'),
 'instrumental':('Labelled as instrumental','Инструментальная версия'),
 'mood':('A match in the collection or genre','Подходит по подборке или жанру')}


class DJView(Gtk.Box):
    def __init__(self,service,artwork,accounts,open_artist):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=12)
        self.service,self.artwork,self.accounts,self.open_artist=service,artwork,accounts,open_artist
        self.active=False;self.syncing=False;self.rows_key=None;self.rows=[];self.size=None;self.columns=2
        content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);self.content=content
        self.scroll=scroll(content);self.pack_start(self.scroll,True,True,0)
        desk=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);desk.get_style_context().add_class('dj-desk')
        header=Gtk.Box(spacing=20);words=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        station=Gtk.Box(spacing=17)
        station.pack_start(label('EMBER DJ','dj-frequency'),False,False,0)
        station.pack_start(label('·  '+text('YOUR OWN FREQUENCY','ЛИЧНАЯ ЧАСТОТА'),'dj-station-note'),False,False,0)
        words.pack_start(station,False,False,0)
        self.title=label(text('Music on your frequency.','Музыка на твоей частоте.'),'dj-title',34)
        self.title.set_line_wrap(True);self.title.set_lines(2)
        words.pack_start(self.title,False,False,0)
        self.reply=label(text(*PHASES['welcome']),'dj-reply',85);self.reply.set_line_wrap(True);self.reply.set_lines(2)
        words.pack_start(self.reply,False,False,0);header.pack_start(words,True,True,0)
        mic_box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6);mic_box.set_valign(Gtk.Align.CENTER)
        self.mic=button('',service.microphone,'dj-microphone',text('Speak to DJ','Сказать пожелание DJ'))
        self.signal=DJSignal(service);self.mic.remove(self.mic.get_child());self.mic.add(self.signal)
        mic_box.pack_start(self.mic,False,False,0)
        self.mic_caption=label(text('SPEAK YOUR WISH','СКАЗАТЬ ПОЖЕЛАНИЕ'),'dj-on-air');self.mic_caption.set_xalign(.5)
        mic_box.pack_start(self.mic_caption,False,False,0)
        self.mic_level=Gtk.ProgressBar();self.mic_level.get_style_context().add_class('dj-micro-level')
        mic_box.pack_start(self.mic_level,False,False,0);header.pack_end(mic_box,False,False,0)
        self.settings_button=button('⚙',self.toggle_settings,accessible=text('DJ settings','Настройки DJ'))
        self.settings_button.set_valign(Gtk.Align.START);header.pack_end(self.settings_button,False,False,0)
        desk.pack_start(header,False,False,0)
        form=Gtk.Box(spacing=10)
        self.entry=Gtk.Entry();self.entry.set_max_length(500);self.entry.set_hexpand(True);self.entry.set_width_chars(20)
        self.entry.set_placeholder_text(text('Relaxing music, something like my favourites, without vocals…',
            'Хочу расслабляющую музыку, в моём вкусе, без вокала…'))
        self.entry.get_style_context().add_class('dj-entry');self.entry.connect('activate',lambda _e:self.submit())
        self.entry.get_accessible().set_name(text('Your musical wish · Enter to start','Пожелание к музыке · Enter — включить'))
        form.pack_start(self.entry,True,True,0)
        self.send=button(text('Make & play my mix','Собрать и включить'),self.submit,'stage-accent')
        self.send.get_style_context().add_class('dj-send');form.pack_start(self.send,False,False,0)
        desk.pack_start(form,False,False,0)
        presets=Gtk.Box(spacing=7);self.presets=[]
        for en,ru,wish_en,wish_ru in (
            ('Unwind','Расслабиться','Relaxing music in my taste','Расслабляющая музыка в моём вкусе'),
            ('Focus','Сосредоточиться','Music to focus, without vocals','Музыка для работы, без вокала'),
            ('More fire','Больше энергии','Give me energetic music','Хочу бодрую музыку'),
            ('Discover','Открытия','New music based on my taste','Новая музыка в моём вкусе')):
            b=button(text(en,ru),lambda wish=text(wish_en,wish_ru):self.preset(wish))
            b.get_style_context().add_class('dj-preset');presets.pack_start(b,False,False,0);self.presets.append(b)
        desk.pack_start(presets,False,False,0)
        status=Gtk.Box(spacing=9);self.spinner=Gtk.Spinner();status.pack_start(self.spinner,False,False,0)
        self.status=label('','dj-status');self.status.set_ellipsize(Pango.EllipsizeMode.END)
        status.pack_start(self.status,True,True,0)
        self.cancel_button=button(text('Cancel','Отменить'),self.cancel)
        self.cancel_button.set_no_show_all(True);status.pack_end(self.cancel_button,False,False,0)
        desk.pack_start(status,False,False,0)
        self.partial=label('','dj-wish',95);self.partial.set_ellipsize(Pango.EllipsizeMode.END)
        self.partial.set_no_show_all(True);desk.pack_start(self.partial,False,False,0)
        content.pack_start(desk,False,False,0)
        self.settings=Gtk.Revealer();self.settings.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.settings.set_transition_duration(250);preferences=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        preferences.get_style_context().add_class('dj-preferences');self.settings.add(preferences)
        toggles=Gtk.Box(spacing=18)
        self.voice_toggle=Gtk.CheckButton(label=text('Voice replies','Ответы голосом'))
        self.ai_toggle=Gtk.CheckButton(label=text('AI for complex wishes','ИИ для сложных пожеланий'))
        for key,b in (('voice',self.voice_toggle),('ai',self.ai_toggle)):
            b.connect('toggled',lambda widget,k=key:service.option(k,widget.get_active()) if not self.syncing else None)
            toggles.pack_start(b,False,False,0)
        self.language=Gtk.ComboBoxText();self.language.append('ru','Русский');self.language.append('en','English')
        self.language.connect('changed',lambda widget:service.option('language',widget.get_active_id()) if not self.syncing else None)
        toggles.pack_start(self.language,False,False,0)
        self.setup_voice=button(text('Prepare voice','Подготовить голос'),lambda:service.setup('voice'))
        self.setup_brain=button(text('Prepare local AI','Подготовить ИИ'),lambda:service.setup('brain'))
        downloads=Gtk.Box(spacing=10)
        downloads.pack_start(self.setup_voice,False,False,0);downloads.pack_start(self.setup_brain,False,False,0)
        preferences.pack_start(toggles,False,False,0);preferences.pack_start(downloads,False,False,0)
        self.setup_progress=Gtk.ProgressBar();self.setup_progress.set_no_show_all(True);preferences.pack_start(self.setup_progress,False,False,0)
        self.privacy=label(text('Your taste stays on this computer. Microphone audio is decoded locally and is not saved.',
            'Твои вкусы остаются на компьютере. Микрофон распознаётся локально, звук не сохраняется.'),'dj-hint',110)
        self.privacy.set_line_wrap(True);preferences.pack_start(self.privacy,False,False,0)
        settings_actions=Gtk.Box(spacing=10)
        settings_actions.pack_start(button(text('Reset taste memory','Сбросить память вкусов'),service.forget),False,False,0)
        settings_actions.pack_start(button(text('Music accounts','Музыкальные аккаунты'),accounts),False,False,0)
        preferences.pack_start(settings_actions,False,False,0);content.pack_start(self.settings,False,False,0)
        self.wish=label('','dj-wish',100);self.wish.set_ellipsize(Pango.EllipsizeMode.END)
        self.wish.set_no_show_all(True);content.pack_start(self.wish,False,False,0)
        heading=Gtk.Box(spacing=10);self.mix_title=label(text('A little closer to you.','Чуть ближе к тебе.'),'stage-artist-section',60)
        heading.pack_start(self.mix_title,True,True,0)
        self.like=button('♥ '+text('Like','Нравится'),lambda:service.feedback(1))
        self.dislike=button(text('Not for me · next','Не моё · дальше'),lambda:service.feedback(-1))
        self.stop_button=button(text('End DJ','Закончить эфир'),service.stop)
        for b in (self.like,self.dislike,self.stop_button):heading.pack_start(b,False,False,0)
        content.pack_start(heading,False,False,0)
        self.list=Gtk.FlowBox();self.list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list.set_homogeneous(True);self.list.set_min_children_per_line(2);self.list.set_max_children_per_line(2)
        self.list.set_row_spacing(10);self.list.set_column_spacing(14);self.list.get_style_context().add_class('dj-flow')
        content.pack_start(self.list,False,False,0)
        self.unsubscribe=service.subscribe(self.changed)
        self.show_all();self.cancel_button.hide();self.partial.hide();self.wish.hide()
        self.changed()

    def activate(self):self.active=True;self.service.activate();self.changed()
    def deactivate(self):self.active=False;self.service.voice.cancel()
    def close(self):self.deactivate();self.unsubscribe()

    def submit(self):
        value=self.entry.get_text().strip()
        if value:self.service.ask(value);self.entry.set_text('')

    def preset(self,value):self.entry.set_text(value);self.submit()
    def toggle_settings(self):self.settings.set_reveal_child(not self.settings.get_reveal_child())
    def cancel(self):
        if self.service.setup_kind:self.service.setup_stop.set()
        else:self.service.cancel();self.service.phase='playing' if self.service.session else 'welcome'
        self.service.changed()

    def changed(self):
        s=self.service;self.syncing=True
        self.voice_toggle.set_active(bool(s.memory.settings.get('voice')))
        self.ai_toggle.set_active(bool(s.memory.settings.get('ai')));self.language.set_active_id(s.language)
        self.syncing=False
        recording=s.voice.phase=='listening';speaking=s.voice.mode=='speak'
        preparing=s.voice.phase=='preparing-voice'
        if recording:self.mic.get_style_context().add_class('dj-listening')
        else:self.mic.get_style_context().remove_class('dj-listening')
        voice_ready=ready('voice',s.language)
        self.mic_caption.set_text(text('CANCEL','ОТМЕНИТЬ') if preparing else text('FINISH RECORDING','ЗАКОНЧИТЬ ЗАПИСЬ') if recording else text('SPEAK YOUR WISH','СКАЗАТЬ ПОЖЕЛАНИЕ') if voice_ready else text('SET UP VOICE','ПОДКЛЮЧИТЬ ГОЛОС'))
        self.mic.get_accessible().set_name(text('Finish recording','Закончить запись') if recording else text('Speak to DJ','Сказать пожелание DJ'))
        self.mic_level.set_fraction(s.voice.level if recording else 0)
        self.mic.set_sensitive(not bool(s.setup_kind))
        message=text('Ready when you are','Готов, когда будешь готов') if s.phase=='welcome' else text(*PHASES.get(s.phase,PHASES['welcome']))
        if s.refilling:message=text('Preparing the next block…','Собираю следующий музыкальный блок…')
        if preparing:message=text('Preparing the microphone…','Готовлю микрофон…')
        if recording:message=text('Microphone on · speak, then press again or pause','Микрофон включён · скажи пожелание, затем нажми ещё раз или сделай паузу')
        elif speaking:message=text('Your DJ is speaking','Твой DJ в эфире')
        if s.setup_kind:
            component={'piper':('DJ voice','голос DJ'),'asr-ru':('Russian recognition','распознавание русского'),
                'asr-en':('English recognition','распознавание английского'),'tts-ru':('Russian voice','русская озвучка'),
                'tts-en':('English voice','английская озвучка'),'llama':('AI runtime','среда ИИ'),
                'brain':('Language model · 1.12 GB','языковая модель · 1,12 ГБ'),'runtime':('Speech runtime','среда распознавания'),
                'ready':('Ready','готово')}.get(s.setup_phase,('components','компоненты'))
            message=text('Preparing: ','Готовлю: ')+text(*component)
        if s.error:message=s.error
        if s.engine and not s.busy and not s.setup_kind and not recording and not speaking:
            message+=text(' · local AI',' · локальный ИИ') if s.engine=='ai' else text(' · mood matching',' · подбор по настроению')
        self.status.set_text(message)
        busy=s.busy or bool(s.setup_kind) or s.voice.phase in ('preparing-voice','preparing-reply')
        self.spinner.start() if busy else self.spinner.stop()
        self.cancel_button.set_visible(busy)
        self.partial.set_text(s.partial);self.partial.set_visible(bool(s.partial) and recording)
        self.wish.set_text(text('Your wish: ','Твоё пожелание: ')+s.prompt);self.wish.set_visible(bool(s.prompt))
        intent=s.intents.get(self.service.host.source)
        self.title.set_text(text(*MOOD_LABEL[intent.mood]) if intent else text('Music on your frequency.','Музыка на твоей частоте.'))
        self.reply.set_text(s.intro or text(*PHASES['welcome']))
        self.mix_title.set_text(NAMES[self.service.host.source]+'  ·  '+text('Your mix','Твой эфир'))
        self.setup_voice.set_sensitive(not s.setup_kind and not voice_ready)
        self.setup_brain.set_sensitive(not s.setup_kind and not (s.models or ready('brain')))
        self.setup_progress.set_fraction(s.setup_fraction if s.setup_kind else 0)
        self.setup_progress.set_visible(bool(s.setup_kind))
        self.stop_button.set_sensitive(s.session)
        playing=bool(self.service.host.length>0)
        self.like.set_sensitive(playing);self.dislike.set_sensitive(playing)
        key=(self.service.host.source,tuple((v.get('uri'),v.get('_reason')) for v in s.items))
        if key!=self.rows_key:self.rows_key=key;self.render_tracks()
        current=s.music.book.current(s.host.source) if s.music.book.active==s.host.source else None
        for row,_play,_add,value in self.rows:
            ctx=row.get_style_context()
            if current and value.get('uri')==current.get('uri'):ctx.add_class('dj-current')
            else:ctx.remove_class('dj-current')

    def render_tracks(self):
        clear(self.list);self.rows=[];s=self.service
        columns=self.columns if s.items else 1
        self.list.set_min_children_per_line(columns);self.list.set_max_children_per_line(columns)
        if not s.items:
            empty=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);empty.set_margin_top(12)
            empty.pack_start(label(text('A good set starts with you.','Хороший сет начинается с тебя.'),'stage-library-title'),False,False,0)
            detail=label(text('Type what you would like to hear, or use the microphone. Personal picks and your Ember listening help shape the next tracks.',
                'Напиши, что хочется услышать, или скажи в микрофон. Личные подборки и прослушивания в Ember помогут выбрать следующие песни.'),'dj-hint',95)
            detail.set_ellipsize(Pango.EllipsizeMode.NONE);detail.set_line_wrap(True);empty.pack_start(detail,False,False,0);self.list.add(empty)
        for index,value in enumerate(s.items[-40:]):
            row=Gtk.Box(spacing=13);row.get_style_context().add_class('dj-track')
            row.pack_start(label(f'{index+1:02d}','dj-track-number'),False,False,0)
            image=Gtk.Image();self.artwork.load(image,value.get('image',''),54,11)
            row.pack_start(image,False,False,0)
            words=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=1)
            play=button(value.get('title',''),lambda item=value:s.play_item(item),'stage-song')
            play.get_child().set_xalign(0);play.get_child().set_ellipsize(Pango.EllipsizeMode.END);play.get_child().set_max_width_chars(36)
            play.get_style_context().add_class('stage-card-title');words.pack_start(play,False,False,0)
            reason=text(*REASONS.get(value.get('_reason'),REASONS['catalogue']))
            caption=label(value.get('artist','')+'  ·  '+reason,'dj-reason',55)
            caption.set_ellipsize(Pango.EllipsizeMode.END);words.pack_start(caption,False,False,0)
            row.pack_start(words,True,True,0);row.pack_start(label(duration(value),'stage-card-subtitle'),False,False,0)
            add=button('+',lambda item=value:s.music.add([item]),'stage-add',text('Add to queue','Добавить в очередь'))
            row.pack_end(add,False,False,0);self.list.add(row);self.rows.append((row,play,add,value))
        self.list.show_all()

    def resize(self,width,height):
        size=height<700 or width<900
        key=(size,width<1000)
        if self.size==key:return
        self.size=key;self.content.set_spacing(8 if size else 12);self.signal.resize(size)
        self.columns=1 if width<1000 else 2
        columns=self.columns if self.service.items else 1
        self.list.set_min_children_per_line(columns);self.list.set_max_children_per_line(columns)
