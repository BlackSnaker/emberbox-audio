"""A quiet, large-type sing-along stage. Only real lyric timing drives words."""
import math
import time
from functools import lru_cache
from itertools import accumulate
from gi.repository import Gtk, Pango
from hardware_controls import MuteToggle, VolumeKnob
from karaoke_audio import KaraokeAudio
from karaoke_timeline import HeardTimeline,PlaybackPoint
from lyrics import active_line
from source_picker import text

CSS=b'''
.karaoke-overline { color: #d5aa58; font-size: 10px; letter-spacing: 3px; }
.karaoke-title { color: #ebdbb2; font-size: 13px; }
.karaoke-hint { color: #a89984; font-size: 11px; }
.karaoke-current { color: #fff1cd; font-size: 48px; font-weight: bold;
  letter-spacing: -1px; text-shadow: 0 2px 22px rgba(250,189,47,.12); }
.karaoke-neighbour { color: #868c79; font-size: 23px; font-weight: bold; }
.karaoke-countdown { color: #fabd2f; font-size: 16px; letter-spacing: 4px; }
.karaoke-panel { border-radius: 24px; padding: 10px 18px;
  background-image: linear-gradient(to bottom right,rgba(255,241,206,.035),rgba(0,0,0,.12));
  box-shadow: inset 0 1px 0 rgba(255,241,206,.035); }
.karaoke-panel combobox button { color: #d5bd85; border-radius: 16px;
  background-image: none; background-color: rgba(255,241,206,.035);
  border: none; box-shadow: none; padding: 7px; font-size: 11px; }
.ember-stage .small-screen .karaoke-current { font-size: 32px; }
.ember-stage .small-screen .karaoke-neighbour { font-size: 17px; }
'''


def caption(value,style):
    label=Gtk.Label(label=value);label.get_style_context().add_class(style)
    label.set_has_tooltip(False)
    return label


@lru_cache(maxsize=8)
def byte_offsets(value):
    return (0,*accumulate(len(character.encode('utf-8')) for character in value))


def word_attributes(line,position):
    """Pango uses UTF-8 bytes. An 120 ms warm fade is purely visual easing;
    words start only at the supplied time, and unknown ends stay unknown.
    """
    attrs=Pango.AttrList()
    key=[];offsets=byte_offsets(line.text)
    for word in line.words:
        if position<word.seconds:continue
        fade=min(1.,max(0.,(position-word.seconds)/.12))
        shade=tuple(round(a+(b-a)*fade)*257 for a,b in zip((255,241,205),(250,189,75)))
        attr=Pango.attr_foreground_new(*shade)
        attr.start_index=offsets[word.start]
        attr.end_index=offsets[word.stop]
        attrs.insert(attr);key.append((word.start,word.stop,shade))
    return attrs,tuple(key)


def moment(state,position):
    """Previous/current/next strings plus exact current index and countdown."""
    if state.status!='ready' or not state.lines:return None
    lines=state.lines;index=active_line(lines,position)
    ended=False
    if index>=0 and lines[index].words:
        last=lines[index].words[-1]
        ended=last.end is not None and position>=last.end
    current=lines[index].text if index>=0 and not ended else ''
    previous=next((line.text for line in reversed(lines[:max(0,index)]) if line.text.strip()),'')
    following=next((line.text for line in lines[max(0,index+1):] if line.text.strip()),'')
    next_line=next((line for line in lines[max(0,index+1):] if line.text.strip()),None)
    countdown=(max(1,math.ceil(next_line.seconds-position)) if not current.strip() and next_line and 0<next_line.seconds-position<=5 else None)
    return previous,current or '♪',following,index if not ended else -1,countdown


class KaraokeView(Gtk.Box):
    def __init__(self,stage):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        self.stage=stage;self.audio=KaraokeAudio(self.audio_changed)
        self.scene_key=None;self.word_key=None;self.scene_index=0;self.last_frame=0.
        self.active=False;self.import_dialog=None;self.import_key=None
        self.small=False;self.cover_key=None
        self.timeline=HeardTimeline();self.heard_playing=False
        self.set_hexpand(True);self.set_vexpand(True)
        self.overline=caption(text('YOUR VOICE. YOUR MOMENT.','ТВОЙ ГОЛОС. ТВОЙ МОМЕНТ.'),'karaoke-overline')
        self.pack_start(self.overline,False,False,0)
        metadata=Gtk.Box(spacing=12);metadata.set_halign(Gtk.Align.CENTER)
        self.cover=Gtk.Image();self.cover.set_size_request(42,42)
        metadata.pack_start(self.cover,False,False,0)
        self.song=caption('','karaoke-title');self.song.set_ellipsize(Pango.EllipsizeMode.END)
        self.song.set_max_width_chars(65);metadata.pack_start(self.song,False,False,0)
        self.pack_start(metadata,False,False,0)
        self.scenes=Gtk.Stack();self.scenes.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.scenes.set_transition_duration(280);self.scenes.set_vhomogeneous(True)
        self.scenes.set_hexpand(True);self.scenes.set_vexpand(True)
        self.labels=[]
        for i in range(2):
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=20)
            box.set_valign(Gtk.Align.CENTER)
            rows=[]
            for style in ('karaoke-neighbour','karaoke-current','karaoke-neighbour'):
                label=caption('',style);label.set_line_wrap(True);label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                label.set_justify(Gtk.Justification.CENTER);label.set_max_width_chars(44)
                label.set_ellipsize(Pango.EllipsizeMode.END);label.set_lines(2 if style=='karaoke-current' else 1)
                label.set_hexpand(True);box.pack_start(label,False,False,0);rows.append(label)
            self.labels.append(rows);self.scenes.add_named(box,str(i))
        self.pack_start(self.scenes,True,True,0)
        self.countdown=caption('','karaoke-countdown');self.countdown.set_size_request(-1,25)
        self.pack_start(self.countdown,False,False,0)
        options=Gtk.Box(spacing=12);options.get_style_context().add_class('karaoke-panel')
        self.voice_toggle=MuteToggle(self.toggle_audio);self.voice_toggle.set_compact(True)
        self.voice_toggle.get_accessible().set_name(text('Vocal reduction','Приглушение вокала'))
        options.pack_start(self.voice_toggle,False,False,0)
        description=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4)
        title=caption(text('Vocal reduction','Приглушение вокала'),'karaoke-title');title.set_xalign(0)
        description.pack_start(title,False,False,0)
        self.audio_note=caption('','karaoke-hint');self.audio_note.set_xalign(0)
        self.audio_note.set_line_wrap(True);self.audio_note.set_max_width_chars(48)
        description.pack_start(self.audio_note,False,False,0)
        options.pack_start(description,True,True,0)
        self.engine_choice=Gtk.ComboBoxText()
        self.engine_choice.append('ai',text('AI · clearer','AI · чище'))
        self.engine_choice.append('stereo',text('Fast · stereo','Быстро · стерео'))
        self.engine_choice.set_active_id(getattr(self.audio,'engine','ai'))
        self.engine_choice.connect('changed',self.choose_engine)
        self.engine_choice.set_valign(Gtk.Align.CENTER);options.pack_start(self.engine_choice,False,False,0)
        self.prepare_button=stage.button(text('Prepare AI','Подготовить AI'),self.prepare_audio,'stage-quiet')
        self.prepare_button.set_valign(Gtk.Align.CENTER);options.pack_start(self.prepare_button,False,False,0)
        self.voice_knob=VolumeKnob(self.set_amount)
        self.voice_knob.get_accessible().set_name(text('Vocal reduction strength','Сила приглушения вокала'))
        self.voice_knob.shown=self.audio.amount;self.voice_knob._render()
        options.pack_start(self.voice_knob,False,False,0)
        self.pack_start(options,False,False,0)
        foot=Gtk.Box(spacing=10)
        self.timing_note=caption('','karaoke-hint');self.timing_note.set_xalign(0)
        self.timing_note.set_line_wrap(True);self.timing_note.set_max_width_chars(70)
        foot.pack_start(self.timing_note,True,True,0)
        self.import_button=stage.button(text('Load LRC','Открыть LRC'),self.choose_file,'stage-quiet')
        foot.pack_end(self.import_button,False,False,0)
        self.auto_button=stage.button(text('Automatic','Автотекст'),self.automatic,'stage-quiet')
        foot.pack_end(self.auto_button,False,False,0)
        self.pack_end(foot,False,False,0)
        self.audio_changed()

    def activate(self):
        self.active=True;self.scene_key=None;self.timeline.clear();self.update()

    def resize(self,small):
        self.small=small
        self.overline.set_no_show_all(small);self.overline.set_visible(not small)
        for rows in self.labels:
            for label in (rows[0],rows[2]):
                label.set_no_show_all(small);label.set_visible(not small)

    def deactivate(self):
        self.active=False;self.audio.disable()
        if self.import_dialog:self.import_dialog.destroy();self.import_dialog=None

    def toggle_audio(self):
        if self.audio.active or self.audio.starting:self.audio.disable()
        else:self.audio.enable(getattr(self.stage.host.sound,'target',None))

    def set_amount(self,value):
        self.audio.set_amount(value);self.audio_changed()

    def choose_engine(self,combo):
        self.audio.set_engine(combo.get_active_id())

    def prepare_audio(self):self.audio.prepare()

    def meter_target(self):
        if not self.active or not self.audio.active or not getattr(self.audio,'process',None):return None
        from stream_target import Target
        return Target('karaoke',self.audio.process.pid,'','karaoke',True)

    def audio_changed(self):
        enabled=self.audio.active or self.audio.starting
        self.voice_toggle.set_state(1.,not enabled,self.audio.available)
        self.voice_knob.set_state(self.audio.amount,False,self.audio.available)
        ai=getattr(self.audio,'engine','ai')=='ai'
        installing=bool(getattr(self.audio,'setup_process',None))
        missing=not getattr(self.audio,'model_ready',True)
        needs_setup=ai and (missing or self.audio.error in ('ai-model-invalid','ai-runtime-invalid','ai-setup-failed'))
        self.prepare_button.set_no_show_all(not needs_setup)
        self.prepare_button.set_visible(needs_setup)
        self.prepare_button.set_sensitive(not installing)
        self.engine_choice.set_sensitive(not installing)
        messages={
            'no-stream':text('Start a song, then enable the filter.','Включи трек, затем включи фильтр.'),
            'multiple-outputs':text('Use one stereo output for this player.','Выбери один стереовыход для плеера.'),
            'stereo-required':text('The filter needs a stereo recording.','Для фильтра нужна стереозапись.'),
            'output-lost':text('Output disconnected. Original routing restored.','Выход отключён. Возвращён обычный звук.'),
            'route-changed':text('Audio routing changed. Filter stopped.','Аудиовыход изменён. Фильтр выключен.'),
            'audio-failed':text('Filter stopped. Original routing restored.','Фильтр остановлен. Возвращён обычный звук.')}
        messages.update({
            'ai-too-slow':text('AI cannot keep up. Original sound restored.','AI не успевает. Возвращён обычный звук.'),
            'ai-model-invalid':text('Model damaged. Prepare AI again.','Модель повреждена. Подготовь AI заново.'),
            'ai-runtime-invalid':text('AI runtime needs repair. Prepare AI again.','Нужно восстановить модуль AI. Нажми «Подготовить AI».'),
            'ai-invalid-output':text('AI stopped. Original sound restored.','AI остановлен. Возвращён обычный звук.'),
            'ai-setup-failed':text('AI setup failed. Retry; details in karaoke-ai/setup.log.','Не удалось подготовить AI. Повтори; подробности в karaoke-ai/setup.log.')})
        note=(messages.get(self.audio.error,text('Filter unavailable.','Фильтр недоступен.')) if self.audio.error else
              text('Preparing the audio filter…','Подключаем звуковой фильтр…') if self.audio.starting else
              text('Vocal reduction on · stereo centre filter','Приглушение включено · фильтр центра стерео') if self.audio.active else
              text('Original sound · switch on to reduce vocals','Оригинальный звук · включи для приглушения голоса') if self.audio.available else
              text('Install PulseAudio utilities to enable the filter.','Для фильтра нужны утилиты PulseAudio.'))
        if installing:
            stage=getattr(self.audio,'setup_stage','')
            note=(text('Downloading UVR model · ','Загружаем модель UVR · ')+f'{getattr(self.audio,"setup_fraction",0)*100:.0f}%'
                  if stage=='download' else text('Installing the private AI runtime…','Устанавливаем отдельный модуль AI…'))
        elif ai and missing and not self.audio.error:
            note=text('Prepare AI once · 30 MB model + private runtime','Подготовь AI один раз · модель 30 МБ + отдельный модуль')
        elif ai and self.audio.starting:
            note=text('Preparing AI and buffering your audio…','Готовим AI и буфер звука…')
        elif ai and self.audio.active:
            note=text('Local UVR AI · delay ≈ ','Локальный AI UVR · задержка ≈ ')+f'{getattr(self.audio,"delay",0):.1f} '+text('s','с')
        self.audio_note.set_text(note)
        h=self.stage.host
        if self.active and hasattr(h,'set_meter_target') and getattr(h.sound,'target',None):
            h.set_meter_target(h.sound.target)
            if h.audio_meter_active():h.meter.start()

    def update(self):
        if not self.active:return
        h=self.stage.host
        self.audio.check_target(getattr(h.sound,'target',None))
        if hasattr(self.audio,'set_muted'):self.audio.set_muted(h.sound.muted)
        now=time.monotonic()
        title,artist,album=h.title.get_text(),h.artist.get_text(),h.album.get_text()
        identity=(h.source,title,artist,album,round(h.length/1e6))
        position=h.position/1e6+(min(1.8,max(0,now-self.stage.anchor)) if h.playing else 0)
        self.timeline.observe(PlaybackPoint(now,identity,title,artist,position,h.length/1e6,h.playing,h.art_url),self.stage.lyrics.state)
        self.import_button.set_sensitive(bool(self.stage.lyrics.key))
        self.frame(now,force=True)

    def show_timing(self,state):
        if state.status=='ready' and state.lines:
            word_sync=any(line.words for line in state.lines)
            note=text('Word timing where supplied','По словам, где есть таймкоды') if word_sync else text('Line timing · word timestamps unavailable','По строкам · таймкодов слов нет')
            self.timing_note.set_text(note+'  ·  '+('LRCLIB' if state.source_url else text('Local LRC','Локальный LRC')))
        elif state.status=='ready' and state.plain:
            self.timing_note.set_text(text('Plain lyrics · no timing available','Обычный текст · без синхронизации'))
        else:self.timing_note.set_text(text('Load an enhanced LRC for precise word timing.','Для точной подсветки слов можно открыть расширенный LRC.'))
        self.auto_button.set_visible(state.status=='error' or state.status=='ready' and not state.source_url)

    def frame(self,now,force=False):
        if not self.active or (not force and now-self.last_frame<1/30):return
        self.last_frame=now
        s=self.stage
        ai=self.audio.active and getattr(self.audio,'engine','ai')=='ai'
        point,state=self.timeline.at(now,getattr(self.audio,'delay',0.) if ai else 0.)
        if point is None:return
        state=state or s.lyrics.state;position=point.position;self.heard_playing=point.playing
        self.song.set_text(point.title+'  ·  '+point.artist);self.show_timing(state)
        if point.art_url!=self.cover_key:
            self.cover_key=point.art_url
            s.artwork.load(self.cover,point.art_url or '',42,9,preserve=True)
        if ai:
            s.position=position;s.progress.set_range(0,max(1,point.length));s.progress.set_value(position)
            current=point.key==self.timeline.points[-1].key
            s.progress.set_sensitive(current and s.host.progress_event.get_sensitive() and point.length>0)
            s.elapsed.set_text(f'{int(position)//60}:{int(position)%60:02}')
            s.total.set_text(f'{int(point.length)//60}:{int(point.length)%60:02}')
            s.playing_caption.set_text(text('Now playing: ','Сейчас: ')+point.title+'  ·  '+point.artist)
            self.import_button.set_sensitive(current and bool(s.lyrics.key))
        scene=moment(state,position)
        if scene:
            previous,current,following,index,countdown=scene
        else:
            values={
                'loading':text('Finding the words…','Ищем нужные слова…'),
                'instrumental':text('Let the music breathe.','Пусть звучит музыка.'),
                'error':text('Words will return.','Слова ещё вернутся.'),
                'idle':text('Play a song. Make it yours.','Включи песню. Спой её по-своему.'),
                'missing':text('Your voice knows the way.','Твой голос знает дорогу.')}
            current=state.plain[:300] if state.status=='ready' and state.plain else values.get(state.status,values['missing'])
            previous=following='';index=-1;countdown=None
        key=(id(state),index,previous,current,following)
        if key!=self.scene_key:
            self.scene_key=key;self.word_key=None;self.scene_index=1-self.scene_index
            rows=self.labels[self.scene_index]
            for label,value in zip(rows,(previous,current,following)):
                label.set_attributes(None);label.set_text(value)
            self.scenes.set_visible_child_name(str(self.scene_index))
        if index>=0 and state.lines[index].words:
            attrs,key=word_attributes(state.lines[index],position)
            if key!=self.word_key:self.labels[self.scene_index][1].set_attributes(attrs);self.word_key=key
        self.countdown.set_text(('●  '*countdown).strip() if countdown else '')

    def choose_file(self):
        if self.import_dialog or not self.stage.lyrics.key:return
        self.import_key=self.stage.lyrics.key
        dialog=self.import_dialog=Gtk.FileChooserDialog(title=text('Lyrics for this recording','Текст для этой записи'),
            transient_for=self.stage.window,action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(text('Cancel','Отмена'),Gtk.ResponseType.CANCEL,text('Open','Открыть'),Gtk.ResponseType.OK)
        filter=Gtk.FileFilter();filter.set_name('LRC · UTF-8');filter.add_pattern('*.lrc');dialog.add_filter(filter)
        dialog.connect('response',self.file_chosen);dialog.show()

    def file_chosen(self,dialog,response):
        path=dialog.get_filename() if response==Gtk.ResponseType.OK else None
        dialog.destroy();self.import_dialog=None
        if path and self.active and self.stage.lyrics.key==self.import_key:self.stage.lyrics.import_file(path)

    def automatic(self):
        self.stage.lyrics.use_automatic()

    def close(self):
        self.deactivate();self.audio.close()
