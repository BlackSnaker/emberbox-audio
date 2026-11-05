"""Warm, two-deck streaming studio with explicit source capabilities."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as C
import json
import time
from gi.repository import Gtk,GLib,Pango
from source_picker import text
from listening_library import label,button,scroll
from discovery_panel import clear
from mashup_catalog import Catalog
from mashup_projects import Projects,recipe
from mashup_client import MashupClient
from cover_pause_paint import bindings,rounded
from hardware_controls import VolumeKnob

CSS=b'''
.mashup-hero { padding: 10px 22px; border-radius: 20px;
 background-image: linear-gradient(115deg,rgba(111,81,43,.5),rgba(37,53,40,.7));
 border: 1px solid rgba(238,208,153,.1); box-shadow: inset 0 1px rgba(255,238,199,.06); }
.mashup-heading { color: #fbefc9; font-size: 24px; font-weight: bold; letter-spacing: -.4px; }
.mashup-kicker { color: #d8b875; font-size: 9px; letter-spacing: 2px; }
.mashup-subtitle { color: #c1b79e; font-size: 12px; }
.mashup-deck { padding: 18px 22px; border-radius: 25px;
 background-image: linear-gradient(to bottom right,rgba(61,65,47,.83),rgba(24,34,27,.92));
 border: 1px solid rgba(233,211,163,.08); box-shadow: inset 0 1px rgba(255,243,211,.05),0 7px 16px rgba(0,0,0,.13); }
.mashup-deck-b { background-image: linear-gradient(to bottom right,rgba(52,64,51,.88),rgba(23,33,28,.94)); }
.mashup-track { color: #f6e8bf; font-size: 22px; font-weight: bold; }
.mashup-artist { color: #c4bba3; font-size: 12px; }
.mashup-wave { background-color: rgba(9,17,12,.55); border-radius: 15px;
 box-shadow: inset 0 3px 8px rgba(0,0,0,.3),inset 0 -1px rgba(246,228,186,.06); padding: 7px 12px; }
.mashup-settings { padding: 17px 22px; border-radius: 22px; background-color: rgba(15,23,17,.46);
 border: 1px solid rgba(235,217,176,.065); box-shadow: inset 0 2px 6px rgba(0,0,0,.12); }
.mashup-field { color: #bdae8d; font-size: 10px; }
.ember-stage .mashup-deck spinbutton, .ember-stage .mashup-settings spinbutton {
 background-image: linear-gradient(to bottom,#172219,#1c271d); background-color: #19221b;
 color: #e6d6aa; border: 1px solid rgba(230,205,153,.11); border-radius: 10px;
 box-shadow: inset 0 2px 5px rgba(0,0,0,.22),inset 0 -1px rgba(244,223,178,.035); }
.ember-stage .mashup-deck spinbutton entry, .ember-stage .mashup-settings spinbutton entry {
 background: transparent; color: #e6d6aa; border: none; box-shadow: none; padding: 7px 9px; }
.ember-stage .mashup-deck spinbutton button, .ember-stage .mashup-settings spinbutton button {
 background-image: linear-gradient(to bottom,#343b2c,#283124); color: #d2bd86;
 border: none; border-left: 1px solid rgba(230,205,153,.05); box-shadow: inset 0 1px rgba(243,227,190,.035); }
.ember-stage .mashup-view combobox button {
 background-image: linear-gradient(to bottom,#3b4231,#2a3427); color: #e0d0a7;
 border: 1px solid rgba(235,213,165,.11); border-radius: 11px; padding: 7px 12px;
 box-shadow: inset 0 1px rgba(245,229,188,.065),0 3px 6px rgba(0,0,0,.12); }
.ember-stage .mashup-view combobox cellview { color: #e0d0a7; }
.ember-stage .mashup-settings checkbutton { color: #d4c6a4; }
.ember-stage .mashup-settings checkbutton check { background-image: linear-gradient(to bottom,#152016,#273022);
 border: 1px solid #635e40; border-radius: 5px; box-shadow: inset 0 2px 4px rgba(0,0,0,.2); }
.ember-stage .mashup-settings checkbutton check:checked { color: #263021;
 background-image: linear-gradient(to bottom,#f0ce7a,#c69943); border-color: #e1bc65; }
.ember-stage .mashup-deck button:link, .ember-stage .mashup-deck button:link label,
.ember-stage .mashup-deck button:visited, .ember-stage .mashup-deck button:visited label { color: #c4af7e; }
.mashup-note { color: #b7ab8e; font-size: 11px; }
.mashup-status { color: #e8c67d; font-size: 12px; }
.mashup-source { color: #b6c493; font-size: 10px; }
.mashup-row { padding: 10px 14px; border-radius: 15px; background-color: rgba(16,25,18,.5); }
.ember-stage entry.mashup-name { background: transparent; border: none; color: #f6e8c2;
 box-shadow: none; font-size: 16px; min-width: 100px; padding: 5px 0; }
.ember-stage .mashup-settings spinbutton, .ember-stage .mashup-deck spinbutton { font-size: 12px; }
.ember-stage .small-screen .mashup-heading { font-size: 21px; }
.ember-stage .small-screen .mashup-hero { padding: 8px 18px; }
.ember-stage .small-screen .mashup-deck { padding: 14px 17px; }
.ember-stage .small-screen .mashup-track { font-size: 18px; }
.ember-stage .small-screen .mashup-settings { padding: 12px 17px; }
'''


class Wave(Gtk.DrawingArea):
    """Static native bars; no GL area, Python cairo dependency or idle loop."""
    def __init__(self,index):
        super().__init__();self.values=[];self.index=index;self.set_size_request(1,66)
        self.get_style_context().add_class('mashup-wave')
        self.c,self.g,self.pointer=bindings();p=C.c_void_p
        self.c.cairo_fill.restype=None;self.c.cairo_fill.argtypes=[p]
        self.callback=C.CFUNCTYPE(C.c_int,p,p,p)(self.draw)
        self.handler=self.g.g_signal_connect_data(self.pointer(self.__gpointer__,None),b'draw',self.callback,None,None,0)
        self.connect('destroy',self.close)
    def set(self,values):self.values=list(values)[:256];self.queue_draw()
    def draw(self,_widget,cr,_data):
        c=self.c;width,height=self.get_allocated_width(),self.get_allocated_height()
        c.cairo_set_source_rgba(cr,.055,.085,.063,.85);rounded(c,cr,1,2,width-2,height-3,13);c.cairo_fill(cr)
        c.cairo_set_source_rgba(cr,.77,.67,.45,.12);c.cairo_set_line_width(cr,1.)
        rounded(c,cr,1.5,2.5,width-3,height-4,12.5);c.cairo_stroke(cr)
        values=self.values or [0.]*64
        color=(.91,.63,.31) if not self.index else (.64,.76,.54)
        c.cairo_set_source_rgba(cr,*color,.2);c.cairo_rectangle(cr,12.,height/2,width-24.,1.);c.cairo_fill(cr)
        if self.values:
            count=min(160,len(values));step=(width-24)/count
            for i in range(count):
                value=min(1.,max(0.,values[i*len(values)//count]))**.6
                h=max(1.,value*(height-22));c.cairo_set_source_rgba(cr,*color,.38+value*.55)
                rounded(c,cr,12+i*step,height/2-h/2,max(1.,step-1.2),h,min(1.4,step/2));c.cairo_fill(cr)
        return False
    def close(self,*_):
        if self.handler:self.g.g_signal_handler_disconnect(self.pointer(self.__gpointer__,None),self.handler);self.handler=0


def field(title,widget):
    box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
    box.pack_start(label(title,'mashup-field'),False,False,0);box.pack_start(widget,False,False,0)
    return box


class LayerKnob(VolumeKnob):
    def __init__(self,changed):
        self.on_change=changed
        super().__init__(self.set_value)
        self.value=self.shown=.75;self._render()
        self.get_accessible().set_name(text('Layer level for the next mix','Уровень дорожки при сборке'))
    def get_value(self):return self.value
    def set_value(self,value):
        self.set_state(max(0,min(1,float(value))),False,True);self.on_change()


class MashupView(Gtk.Box):
    def __init__(self,stage):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=12)
        self.get_style_context().add_class('mashup-view')
        self.stage=stage;self.active=False;self.closed=False;self.loading=False;self.request=0;self.slot=0
        self.catalog=Catalog();self.store=Projects();self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='mashup-catalogue')
        self.search_future=None;self.catalog_page=0;self.catalogue_query=None
        self.ai_setup_requested=False;self.ai_setup_state=None
        self.client=MashupClient(self.changed);self.autoplay=False;self.shown_ready=None;self.return_meter=None;self.dirty=False
        self.project={'id':'','name':'','tracks':[],'whole':False,'length':30.,'auto':True,'tempo':0.,'shift':0,'offset':0.}
        self.tracks=[None,None];self.decks=[];self.current_page='studio'
        self.tabs=Gtk.Box(spacing=6)
        for key,caption in [('studio',text('Studio','Студия')),('catalogue',text('Free catalogue','Бесплатный каталог')),('projects',text('My projects','Мои проекты'))]:
            self.tabs.pack_start(button(caption,lambda k=key:self.page(k)),False,False,0)
        self.pack_start(self.tabs,False,False,0)
        self.pages=Gtk.Stack();self.pages.set_hhomogeneous(False);self.pages.set_vhomogeneous(False)
        self.pages.set_transition_type(Gtk.StackTransitionType.CROSSFADE);self.pages.set_transition_duration(300)
        self.pack_start(self.pages,True,True,0)
        self.content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14)
        self.studio=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        self.studio.pack_start(scroll(self.content),True,True,0)
        self.pages.add_named(self.studio,'studio')
        hero=self.hero=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3);hero.get_style_context().add_class('mashup-hero')
        hero.pack_start(label('EMBER LAB  /  MASHUP STUDIO','mashup-kicker'),False,False,0)
        hero.pack_start(label(text('Two songs. One spark.','Два трека. Одна искра.'),'mashup-heading'),False,False,0)
        hero.pack_start(label(text('A voice, a rhythm, a new story.','Голос, ритм и новая история.'),'mashup-subtitle'),False,False,0)
        self.content.pack_start(hero,False,False,0)
        self.deck_row=Gtk.Box(spacing=14);self.content.pack_start(self.deck_row,False,False,0)
        for index in (0,1):self.build_deck(index)
        settings=Gtk.Box(spacing=18);settings.get_style_context().add_class('mashup-settings')
        self.whole=Gtk.CheckButton(label=text('Whole songs','Целые песни'))
        self.length=Gtk.SpinButton.new_with_range(5,120,5);self.length.set_value(30)
        self.auto=Gtk.CheckButton(label=text('Auto mix','Автомешап'));self.auto.set_active(True)
        self.tempo=Gtk.SpinButton.new_with_range(0,200,1)
        self.shift=Gtk.SpinButton.new_with_range(-6,6,1)
        self.offset=Gtk.SpinButton.new_with_range(-10,10,.05)
        self.shift.set_value(0);self.offset.set_value(0)
        self.setting_fields=[]
        for title,widget in [(text('Material','Материал'),self.whole),(text('Clip · seconds','Фрагмент · сек'),self.length),
            (text('Alignment','Сведение'),self.auto),('BPM · 0 = Auto',self.tempo),
            (text('Pitch B · semitones','Тон B · полутоны'),self.shift),(text('Entry B · seconds','Вход B · сек'),self.offset)]:
            child=field(title,widget);settings.pack_start(child,True,True,0);self.setting_fields.append(child)
        self.settings_box=settings;self.content.pack_start(settings,False,False,0)
        self.whole.connect('toggled',lambda *_:self.length.set_sensitive(not self.whole.get_active()))
        for widget in (self.whole,self.auto):widget.connect('toggled',lambda *_:self.edited())
        for widget in (self.length,self.tempo,self.shift,self.offset):widget.connect('value-changed',lambda *_:self.edited())
        actions=self.actions=Gtk.Box(spacing=10)
        self.prepare_button=button(text('Build & listen','Собрать и слушать'),self.prepare,'stage-accent')
        self.preview_button=button('▶',self.client.toggle,accessible=text('Play or pause mashup','Воспроизвести или приостановить мешап'))
        self.cancel_button=button(text('Stop','Остановить'),self.stop)
        self.name=Gtk.Entry();self.name.set_placeholder_text(text('Project name','Название проекта'));self.name.get_style_context().add_class('mashup-name')
        self.name.set_hexpand(True)
        self.save_button=button(text('Save project','Сохранить проект'),self.save)
        for widget in (self.prepare_button,self.preview_button,self.cancel_button):actions.pack_start(widget,False,False,0)
        actions.pack_start(self.name,True,True,0);actions.pack_end(self.save_button,False,False,0)
        self.studio.pack_start(actions,False,False,0)
        self.status=label('','mashup-status');self.status.set_line_wrap(True);self.studio.pack_start(self.status,False,False,0)
        self.progress=Gtk.ProgressBar();self.progress.set_no_show_all(True);self.studio.pack_start(self.progress,False,False,0)
        self.ai_button=button(text('Prepare vocal AI','Подготовить AI для вокала'),self.prepare_ai)
        self.ai_button.set_no_show_all(True);self.studio.pack_start(self.ai_button,False,False,0)
        self.note=label(text('Free CC BY streams from ccMixter. Projects retain the original artists and source links.',
            'Бесплатные потоки CC BY из ccMixter. Проекты сохраняют авторов и ссылки на оригиналы.'),'mashup-note')
        self.note.set_line_wrap(True);self.content.pack_start(self.note,False,False,0)
        self.catalogue=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        self.pages.add_named(self.catalogue,'catalogue')
        bar=Gtk.Box(spacing=10)
        self.search_entry=Gtk.SearchEntry();self.search_entry.set_placeholder_text(text('Title, artist or mood','Название, автор или настроение'))
        self.search_entry.connect('activate',lambda *_:self.search());bar.pack_start(self.search_entry,True,True,0)
        self.kind=Gtk.ComboBoxText()
        for key,name in [('vocal',text('Vocals','Акапеллы')),('instrumental',text('Instrumentals','Инструменталы')),('song',text('Songs','Треки'))]:self.kind.append(key,name)
        self.kind.set_active_id('vocal');bar.pack_start(self.kind,False,False,0)
        bar.pack_start(button(text('Search','Найти'),self.search,'stage-accent'),False,False,0)
        self.catalogue.pack_start(bar,False,False,0)
        self.catalog_status=label(text('Choose two tracks from the free catalogue.','Выбери два трека из бесплатного каталога.'),'mashup-note')
        self.catalog_status.set_line_wrap(True);self.catalogue.pack_start(self.catalog_status,False,False,0)
        self.results=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=7)
        self.catalogue.pack_start(scroll(self.results),True,True,0)
        self.more=button(text('More tracks','Ещё треки'),lambda:self.search(append=True))
        self.more.set_sensitive(False);self.catalogue.pack_end(self.more,False,False,0)
        self.projects=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        self.pages.add_named(scroll(self.projects),'projects')
        self.show_all();self.progress.hide();self.ai_button.hide();self.pages.set_visible_child_name('studio');self.changed()

    def build_deck(self,index):
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);box.set_hexpand(True)
        box.get_style_context().add_class('mashup-deck')
        if index:box.get_style_context().add_class('mashup-deck-b')
        box.pack_start(label(('B  /  '+text('THE FOUNDATION','ОСНОВА')) if index else 'A  /  '+text('THE VOICE','ГОЛОС'),'mashup-kicker'),False,False,0)
        title=label(text('Another possibility','Другая возможность') if index else text('It starts with a voice','Всё начинается с голоса'),'mashup-track',36)
        box.pack_start(title,False,False,0)
        artist=label(text('No track selected','Трек ещё не выбран'),'mashup-artist',45);box.pack_start(artist,False,False,0)
        wave=Wave(index);box.pack_start(wave,False,False,0)
        controls=Gtk.Box(spacing=12)
        role=Gtk.ComboBoxText()
        for key,value in [('vocal',text('Vocal','Вокал')),('instrumental',text('Instrumental','Инструментал')),('song',text('Full mix','Целиком'))]:role.append(key,value)
        role.set_active_id('instrumental' if index else 'vocal')
        start=Gtk.SpinButton.new_with_range(0,599,.5)
        gain=LayerKnob(self.edited);gain.set_halign(Gtk.Align.CENTER)
        role.connect('changed',lambda *_:self.edited());start.connect('value-changed',lambda *_:self.edited())
        controls.pack_start(field(text('Layer','Слой'),role),False,False,0)
        controls.pack_start(field(text('Start · seconds','Начало · сек'),start),False,False,0)
        level=field(text('Level','Уровень'),gain);level.set_halign(Gtk.Align.END)
        controls.pack_end(level,False,False,0)
        box.pack_start(controls,False,False,0)
        credit=label('','mashup-source');credit.set_line_wrap(True);box.pack_start(credit,False,False,0)
        links=Gtk.Box(spacing=6)
        choose=button(text('Choose stream','Выбрать поток'),lambda i=index:self.choose(i),'stage-accent')
        current=button(text('From player','Из плеера'),lambda i=index:self.from_player(i))
        origin=Gtk.LinkButton.new_with_label('https://ccmixter.org/',text('Source & credits ↗','Оригинал и авторы ↗'))
        origin.set_has_tooltip(False);origin.get_style_context().add_class('stage-artist-link')
        links.pack_start(choose,False,False,0);links.pack_start(current,False,False,0);links.pack_end(origin,False,False,0)
        box.pack_start(links,False,False,0);self.deck_row.pack_start(box,True,True,0)
        self.decks.append(dict(box=box,title=title,artist=artist,wave=wave,role=role,start=start,gain=gain,credit=credit,origin=origin))

    def page(self,key):
        self.current_page=key;self.pages.set_visible_child_name(key)
        if key=='projects':self.render_projects()

    def activate(self):self.active=True;self.changed()

    def deactivate(self):
        self.active=False;self.request+=1;self.loading=False;self.stop()

    def resize(self,width,height):
        self.deck_row.set_orientation(Gtk.Orientation.VERTICAL if width<950 else Gtk.Orientation.HORIZONTAL)
        self.settings_box.set_orientation(Gtk.Orientation.VERTICAL if width<800 else Gtk.Orientation.HORIZONTAL)

    def choose(self,index):
        self.slot=index;self.kind.set_active_id('instrumental' if index else 'vocal');self.page('catalogue')
        if not self.results.get_children() or self.catalogue_query!=(self.search_entry.get_text(),self.kind.get_active_id()):self.search()

    def search(self,append=False):
        self.request+=1;generation=self.request
        self.catalog_status.set_text(text('Opening the free catalogue…','Открываю бесплатный каталог…'))
        term=self.search_entry.get_text();kind=self.kind.get_active_id()
        if not append or self.catalogue_query!=(term,kind):self.catalog_page=0;append=False
        else:self.catalog_page+=1
        self.catalogue_query=(term,kind);self.more.set_sensitive(False)
        if self.search_future:self.search_future.cancel()
        future=self.search_future=self.pool.submit(self.catalog.search,term,kind,self.catalog_page)
        def done(future):
            try:values,error=future.result(),None
            except Exception:values,error=[],True
            def apply():
                if self.closed or generation!=self.request:return False
                if not append:clear(self.results)
                self.catalog_status.set_text(text('Catalogue unavailable. Retry in a moment.','Каталог пока недоступен. Попробуй ещё раз.') if error else
                    text(f'CC BY · {len(values)} streams · choose for deck {"AB"[self.slot]}',f'CC BY · потоков: {len(values)} · выбор для дорожки {"AB"[self.slot]}'))
                for item in values:
                    row=Gtk.Box(spacing=12);row.get_style_context().add_class('mashup-row')
                    names=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4);names.set_hexpand(True)
                    names.pack_start(label(item['title'],'stage-card-title',70),False,False,0)
                    names.pack_start(label(item['artist']+'  ·  CC BY  ·  '+str(round(item['duration']))+' s','mashup-artist',80),False,False,0)
                    row.pack_start(names,True,True,0)
                    row.pack_end(button(text('Select','Выбрать'),lambda v=item:self.select(v),'stage-accent'),False,False,0)
                    self.results.pack_start(row,False,False,0)
                self.more.set_sensitive(not error and self.catalog_page<10)
                self.results.show_all();return False
            GLib.idle_add(apply)
        future.add_done_callback(done)

    def select(self,item,index=None):
        index=self.slot if index is None else index;self.stop();self.tracks[index]=dict(item)
        self.update_deck(index);self.page('studio');self.changed()

    def update_deck(self,index):
        item=self.tracks[index];deck=self.decks[index]
        if item is None:return
        deck['title'].set_text(item['title']);deck['artist'].set_text(item.get('artist',''))
        permitted=item.get('source')=='ccmixter'
        deck['credit'].set_text('CC BY · ccMixter' if permitted else text(
            'Recipe only · this connection does not provide editing access',
            'Для проекта · это подключение не предоставляет доступ к обработке'))
        deck['origin'].set_uri(item.get('page') or 'https://ccmixter.org/')
        deck['wave'].set([])

    def from_player(self,index):
        from music_library import snapshot
        item=snapshot(self.stage.host)
        if not item.get('valid'):
            self.status.set_text(text('Start a song in the player first.','Сначала выбери песню в плеере.'));return
        source=self.stage.host.source
        value={'source':source,'id':str(item.get('id') or item.get('uri') or ''),
            'title':str(item.get('title') or ''),'artist':str(item.get('artist') or '')}
        self.select(value,index)

    def current(self):
        project={**self.project,'name':self.name.get_text(),'whole':self.whole.get_active(),
            'length':self.length.get_value(),'auto':self.auto.get_active(),'tempo':self.tempo.get_value(),
            'shift':self.shift.get_value_as_int(),'offset':self.offset.get_value(),'tracks':[]}
        for item,deck in zip(self.tracks,self.decks):
            if item:project['tracks'].append({**item,'role':deck['role'].get_active_id(),
                'start':deck['start'].get_value(),'gain':deck['gain'].get_value()})
        return recipe(project)

    def edited(self):
        if hasattr(self,'client') and self.client.state=='ready':
            self.dirty=True;self.changed()

    def prepare_ai(self):
        self.ai_setup_requested=True;self.ai_setup_state=None
        self.stage.karaoke.audio.prepare();self.poll_setup()

    def poll_setup(self):
        if not self.ai_setup_requested or not self.active:return
        audio=self.stage.karaoke.audio
        state=(bool(audio.setup_process),audio.setup_stage,round(audio.setup_fraction,2),audio.model_ready)
        if state==self.ai_setup_state:return
        self.ai_setup_state=state
        self.ai_button.set_sensitive(not state[0]);self.progress.set_visible(state[0])
        if state[0]:
            self.status.set_text(text('Preparing vocal AI · the player stays available','Подготавливаю AI для вокала · плеер остаётся доступен')+'…')
            self.progress.set_fraction(state[2])
        else:
            self.ai_setup_requested=False;self.ai_button.set_visible(not state[3])
            self.status.set_text(text('Vocal AI is ready · build your mashup','AI для вокала готов · можно собирать мешап') if state[3] else
                text('AI setup failed. Check the connection and retry.','Подготовка AI прервалась. Проверь соединение и попробуй ещё раз.'))

    def prepare(self):
        if not all(self.tracks):return
        if any(v.get('source')!='ccmixter' for v in self.tracks):
            self.status.set_text(text('These service tracks can be saved in a recipe; editing access is not available.',
                'Эти песни можно сохранить в проекте; доступ к обработке сервис пока не предоставляет.'));return
        self.stop();self.dirty=False;self.autoplay=True;self.client.prepare(self.current())

    def stop(self):
        self.autoplay=False;self.shown_ready=None;self.client.stop()
        meter=getattr(self.stage.host,'meter',None)
        if meter and self.return_meter is not None:meter.set_target(self.return_meter)
        self.return_meter=None
        if hasattr(self,'status'):self.changed()

    def meter_target(self):
        if self.client.playing and self.client.process:
            from stream_target import Target
            return Target(source='mashup',pid=self.client.process.pid,player='mashup')
        return None

    def changed(self):
        if self.closed:return
        client=self.client;busy=client.state=='preparing';ready=client.state=='ready'
        target=self.meter_target()
        if target is not None:
            meter=getattr(self.stage.host,'meter',None)
            if meter:meter.set_target(target)
        if ready and self.shown_ready is not client.ready:
            self.shown_ready=client.ready
            for index,item in enumerate(client.ready.get('tracks',[])[:2]):
                self.tracks[index]=dict(item);self.update_deck(index)
            for index,values in enumerate(client.ready.get('waves',[])):self.decks[index]['wave'].set(values)
            if self.autoplay:
                self.autoplay=False
                if self.stage.host.playing:self.stage.host.on_action(None,'toggle')
                meter=getattr(self.stage.host,'meter',None)
                if meter:
                    from stream_target import Target
                    self.return_meter=getattr(meter,'target',None)
                    meter.set_target(Target(source='mashup',pid=client.process.pid,player='mashup'))
                client.send('volume',value=client.volume);client.send('mute',muted=client.muted);client.play();return
        labels={'source':('Checking the source','Проверяю источник'),'load':('Loading stream','Загружаю поток'),
            'analyse':('Finding rhythm and harmony','Определяю ритм и тональность'),
            'separate':('Preparing the layers','Разделяю дорожки'),'align':('Aligning the songs','Согласую звучание'),
            'mix':('Creating the mashup','Собираю мешап')}
        if busy:
            key=client.stage.split('-')[0];caption=text(*labels.get(key,labels['mix']))
            if '-' in client.stage:caption+=' · '+'AB'[int(client.stage.rsplit('-',1)[1])]
            self.status.set_text(caption+'…')
        elif ready:
            proposal=client.ready.get('plan') or {};bpm=proposal.get('tempo')
            self.status.set_text(text('Settings changed · apply to hear the new mix','Настройки изменены · примени, чтобы услышать новое сведение') if self.dirty else
                text('Mashup ready','Мешап готов')+('  ·  '+str(round(bpm,1))+' BPM' if bpm else '  ·  '+text('Original tempos','Исходный темп')))
        elif client.state=='error':
            messages={'ai-missing':('Prepare the optional vocal AI first.','Для этого трека сначала подготовь AI для вокала.'),
                'tempo-too-far':('Tempos are too far apart. Turn off Auto mix or choose a closer pair.','Темпы сильно различаются. Выключи автомешап или выбери более близкую пару.'),
                'rubberband-missing':('FFmpeg needs its Rubber Band filter for tempo/pitch alignment.','Для согласования темпа и тона нужен FFmpeg с фильтром Rubber Band.'),
                'source-not-editable':('This source does not provide editing access.','Источник не предоставляет доступ к обработке.'),
                'audio-duration-limit':('Choose a track shorter than 10 minutes or a clip.','Выбери песню короче 10 минут или фрагмент.'),
                'fragment-outside-track':('The selected start is outside this track.','Начало фрагмента находится за пределами трека.'),
                'track-unavailable':('The track or its editing permission is unavailable.','Трек или разрешение на обработку сейчас недоступны.')}
            self.status.set_text(text(*messages.get(client.error,('Preparation failed. The streams may be temporarily unavailable.','Подготовка прервалась. Потоки могут быть временно недоступны.'))))
        else:self.status.set_text(text('Choose a voice and a foundation. No subscription required.','Выбери голос и основу. Подписка не нужна.'))
        self.prepare_button.set_sensitive(all(self.tracks) and not busy)
        self.prepare_button.set_label(text('Apply & listen','Применить и слушать') if self.dirty else text('Build & listen','Собрать и слушать'))
        self.settings_box.set_sensitive(not busy)
        for deck in self.decks:
            for key in ('role','start','gain'):deck[key].set_sensitive(not busy)
        self.preview_button.set_sensitive(ready)
        caption='Ⅱ' if client.playing else '▶'
        if self.preview_button.get_label()!=caption:self.preview_button.set_label(caption)
        self.cancel_button.set_sensitive(busy or ready)
        self.progress.set_visible(busy)
        if busy:
            if client.fraction is not None:self.progress.set_fraction(client.fraction)
            else:self.progress.pulse()
        self.ai_button.set_visible(client.error=='ai-missing')

    def save(self):
        try:
            value=self.current()
            if len(value['tracks'])!=2:raise ValueError('two-tracks-required')
            if not value['name']:value['name']=self.tracks[0]['title']+' × '+self.tracks[1]['title']
            self.project=self.store.save(value);self.status.set_text(text('Project saved · sources, authors and settings','Проект сохранён · источники, авторы и настройки'))
        except (ValueError,OSError):self.status.set_text(text('The project could not be saved. Existing projects are intact.','Не удалось сохранить проект. Прежние проекты сохранены.'))

    def render_projects(self):
        clear(self.projects)
        for item in self.store.items:
            row=Gtk.Box(spacing=12);row.get_style_context().add_class('mashup-row')
            row.pack_start(label(item['name'],'stage-card-title',70),True,True,0)
            row.pack_end(button(text('Open','Открыть'),lambda value=item:self.open_project(value)),False,False,0)
            self.projects.pack_start(row,False,False,0)
        if not self.store.items:self.projects.pack_start(label(text('Your musical sketches will live here.','Здесь будут твои музыкальные эскизы.'),'mashup-note'),False,False,0)
        self.projects.show_all()

    def open_project(self,item):
        self.stop();self.project=json.loads(json.dumps(item));self.name.set_text(item['name'])
        self.tracks=[None,None]
        for index,value in enumerate(item['tracks']):
            self.tracks[index]=dict(value);self.update_deck(index);deck=self.decks[index]
            deck['role'].set_active_id(value['role']);deck['start'].set_value(value['start']);deck['gain'].set_value(value['gain'])
        for widget,key in [(self.length,'length'),(self.tempo,'tempo'),(self.shift,'shift'),(self.offset,'offset')]:widget.set_value(item[key])
        self.whole.set_active(item['whole']);self.auto.set_active(item['auto']);self.page('studio');self.changed()

    def close(self):
        self.closed=True;self.active=False;self.request+=1;self.stop();self.client.close();self.pool.shutdown(wait=False,cancel_futures=True)
