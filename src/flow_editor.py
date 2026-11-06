"""An in-playlist two-deck transition desk; static curves, real audition."""
from gi.repository import Gtk,Pango
from source_picker import text
from flow_control import FlowControl
from flow_plans import recipe
from flow_hardware import TimeDial,BeatSwitch,screw
from flow_timeline import FlowTimeline
from flow_eq_panel import EQPanel

CSS=b'''
.flow-desk { background-image: linear-gradient(145deg,rgba(51,53,46,.94),rgba(22,27,23,.96));
 border: 1px solid rgba(235,219,178,.12); border-radius: 28px; padding: 16px;
 box-shadow: inset 0 1px rgba(255,239,201,.06),0 5px 12px rgba(0,0,0,.12); }
.flow-desk-title { font-size: 23px; font-weight: bold; color: #f1e5be; }
.flow-deck { background-image: linear-gradient(145deg,rgba(14,19,16,.65),rgba(39,43,34,.7));
 border: 1px solid rgba(235,219,178,.045); border-radius: 22px; padding: 12px;
 box-shadow: inset 0 2px 5px rgba(0,0,0,.2),0 1px rgba(235,219,178,.04); }
.flow-desk .flow-envelope { background: #0a100d; border-radius: 19px; padding: 7px;
 border: 1px solid rgba(179,189,153,.07); box-shadow: inset 2px 3px 8px rgba(0,0,0,.65),0 1px rgba(240,224,179,.08); }
.flow-engraving { font-size: 9px; letter-spacing: 1.5px; color: #a5a18b; }
.flow-cover { background-image: linear-gradient(140deg,#101613,#30392c); padding: 5px; border-radius: 13px;
 box-shadow: inset 0 2px 6px rgba(0,0,0,.6),0 1px rgba(240,224,179,.08); }
.flow-desk button.flow-selector { background-image: linear-gradient(145deg,#3b4438,#262e26); border: 1px solid #161d17;
 border-radius: 17px; padding: 7px 13px; color: #b8b5a1; font-size: 11px; box-shadow: 1px 2px 3px rgba(0,0,0,.25),inset 0 1px rgba(244,232,193,.08); }
.flow-desk button.flow-selector:checked { background-image: linear-gradient(150deg,#1c241d,#2c3427);
 color: #f2cb7f; box-shadow: inset 1px 2px 4px rgba(0,0,0,.5),0 1px rgba(240,224,179,.08); }
.flow-desk button.flow-selector:hover { color: #f2dba7; }
.flow-instrument { background-image: linear-gradient(155deg,rgba(12,19,14,.75),rgba(44,51,39,.5)); padding: 8px 15px;
 border-radius: 22px; border: 1px solid rgba(5,12,7,.6); box-shadow: inset 1px 2px 4px rgba(0,0,0,.28),0 1px rgba(240,224,179,.06); }
.flow-time-display { color: #efc879; font-family: monospace; font-size: 18px; letter-spacing: 1px; }
.nocturne-theme .flow-instrument { background-image: linear-gradient(145deg,#121717,#242929); }
.nocturne-theme .flow-desk button.flow-selector { background-image: linear-gradient(145deg,#343b38,#242c28); }
.nocturne-theme .flow-desk button.flow-selector:checked { background-image: linear-gradient(145deg,#151d18,#283025); }

.flow-desk combobox button { border-radius: 17px; background-image: linear-gradient(135deg,#34382e,#242a22);
 color: #ebdbb2; border: 1px solid rgba(235,219,178,.08); box-shadow: none; }
.flow-desk scale trough { background: #121812; border-radius: 5px; min-height: 5px; }
.flow-desk scale highlight { background: #d8ad53; border: none; border-radius: 5px; }
.flow-desk scale slider { background-image: linear-gradient(145deg,#f5d58c,#bb8d3c); border: none;
 min-width: 14px; min-height: 14px; box-shadow: 0 2px 3px rgba(0,0,0,.25); }
.flow-desk checkbutton { color: #d5c8aa; }
.flow-desk checkbutton check { background: #171c18; border: 1px solid #6f6c55; border-radius: 5px; box-shadow: inset 0 1px 3px rgba(0,0,0,.3); }
.flow-desk checkbutton check:checked { background: #c49e50; color: #20271e; }
.flow-desk-compact { padding: 10px; }
.flow-desk-compact .flow-deck { padding: 7px; }
.flow-desk-compact .flow-desk-title { font-size: 17px; }
.flow-desk-compact button.stage-accent, .flow-desk-compact button.stage-quiet { padding: 5px 10px; min-height: 14px; }
.flow-desk-compact combobox button { padding: 3px 7px; min-height: 14px; }
.nocturne-theme .flow-desk { background-image: linear-gradient(145deg,#232626,#171a1a); }
.nocturne-theme .flow-deck { background-image: linear-gradient(145deg,#101313,#202424); }
.nocturne-theme .flow-desk combobox button { background-image: linear-gradient(145deg,#303435,#222627); }
'''


def label(value,style='stage-library-note'):
    w=Gtk.Label(label=value);w.set_xalign(0);w.get_style_context().add_class(style)
    w.set_ellipsize(Pango.EllipsizeMode.END);w.set_width_chars(1);return w


def button(value,callback,style='stage-quiet'):
    w=Gtk.Button(label=value);w.get_style_context().add_class(style)
    w.set_has_tooltip(False);w.connect('clicked',lambda *_:callback());return w


class FlowEditor(Gtk.Box):
    def __init__(self,service,artwork,key,items,back):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        self.get_style_context().add_class('flow-desk')
        self.service=service;self.flow=service.flow;self.artwork=artwork;self.key=key;self.items=items
        self.index=0;self.updating=False;self.closed=False
        top=Gtk.Box(spacing=12)
        top.pack_start(Gtk.Image.new_from_pixbuf(screw()),False,False,0)
        top.pack_start(label('EMBERFLOW / '+text('TRANSITION DESK','МАСТЕРСКАЯ ПЕРЕХОДОВ'),'stage-library-source'),True,True,0)
        top.pack_end(Gtk.Image.new_from_pixbuf(screw()),False,False,0)
        self.lamp=FlowControl(self.flow);top.pack_end(self.lamp,False,False,0)
        top.pack_end(button('‹ '+text('Tracks','К трекам'),back),False,False,0);self.pack_start(top,False,False,0)
        title=Gtk.Box(spacing=12);title.pack_start(label(text('The space between songs.','Между песнями — твой почерк.'),'flow-desk-title'),True,True,0)
        self.auto_button=button('✦ '+text('Let Ember choose','Подобрать с Эмбер'),self.automatic,'stage-accent')
        title.pack_end(self.auto_button,False,False,0);self.pack_start(title,False,False,0)
        self.pairs=Gtk.ComboBoxText();self.pairs.set_hexpand(True)
        for index,(a,b) in enumerate(zip(items,items[1:])):
            self.pairs.append_text(f'{index+1:02d}  {a["title"][:55]}  →  {b["title"][:55]}')
        # The popup never dictates the width of the listening room.
        for renderer in self.pairs.get_cells():
            if isinstance(renderer,Gtk.CellRendererText):renderer.set_property('ellipsize',Pango.EllipsizeMode.END);renderer.set_property('width-chars',32)
        self.pairs.connect('changed',self.choose);self.pack_start(self.pairs,False,False,0)
        decks=self.decks=Gtk.Box(spacing=16);decks.set_homogeneous(True);self.deck_images=[];self.deck_titles=[];self.deck_artists=[]
        for name in (text('OUTGOING','УХОДЯЩИЙ'),text('INCOMING','СЛЕДУЮЩИЙ')):
            deck=Gtk.Box(spacing=14);deck.get_style_context().add_class('flow-deck')
            image=Gtk.Image();image.set_size_request(60,60);frame=Gtk.Box();frame.get_style_context().add_class('flow-cover');frame.pack_start(image,False,False,0);deck.pack_start(frame,False,False,0);self.deck_images.append(image)
            names=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6);names.pack_start(label(name,'stage-library-source'),False,False,0)
            song=label('','stage-card-title');artist=label('');self.deck_titles.append(song);self.deck_artists.append(artist)
            names.pack_start(song,False,False,0);names.pack_start(artist,False,False,0);deck.pack_start(names,True,True,0)
            decks.pack_start(deck,True,True,0)
        self.pack_start(decks,False,False,0)
        self.timeline=FlowTimeline(self.timeline_changed);self.pack_start(self.timeline,False,False,0)
        controls=self.controls=Gtk.Box(spacing=18);controls.set_hexpand(True)
        options=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);controls.pack_start(options,True,True,0)
        self.mode=Gtk.ComboBoxText();self.shape=Gtk.ComboBoxText()
        self.mode_buttons={};self.shape_buttons={}
        for combo,values,buttons in ((self.mode,(('auto','Ember · auto','Эмбер · авто'),('manual','By hand','Вручную'),('cut','No mix','Без сведения')),self.mode_buttons),
                (self.shape,(('shared','Shared phrase','Общий момент'),('smooth','Dissolve','Растворение')),self.shape_buttons)):
            selectors=Gtk.Box(spacing=6);selectors.set_homogeneous(True)
            for key,en,ru in values:
                combo.append(key,text(en,ru))
                b=Gtk.ToggleButton(label=text(en,ru));b.get_style_context().add_class('flow-selector');b.set_has_tooltip(False)
                b.connect('clicked',lambda w,c=combo,k=key:self.select_choice(c,k))
                buttons[key]=b;selectors.pack_start(b,True,True,0)
            options.pack_start(selectors,False,False,0)
        instruments=Gtk.Box(spacing=12);instruments.get_style_context().add_class('flow-instrument')
        self.length=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,1,8,.1)
        self.knob=TimeDial(lambda v:self.length.set_value(round((1+7*v)*2)/2))
        instruments.pack_start(self.knob,False,False,0)
        dial_names=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=7)
        dial_names.pack_start(label(text('OVERLAP','ВРЕМЯ СВЕДЕНИЯ'),'flow-engraving'),False,False,0)
        self.length_label=label('','flow-time-display');dial_names.pack_start(self.length_label,False,False,0)
        dial_names.pack_start(label(text('1—8 s · drag / scroll','1—8 с · поворот / колесо')),False,False,0)
        instruments.pack_start(dial_names,True,True,0)
        self.beats=BeatSwitch();instruments.pack_end(self.beats,False,False,0)
        beat_name=label(text('BEAT\nSYNC','РИТМ\nСИНХР.'),'flow-engraving');instruments.pack_end(beat_name,False,False,0)
        controls.pack_start(instruments,True,True,0);self.pack_start(controls,False,False,0)
        self.eq_panel=EQPanel(self.edit);self.pack_start(self.eq_panel,False,False,0)
        self.eq_panel.toggle.connect('toggled',lambda b:(self.decks.set_no_show_all(b.get_active()),self.decks.set_visible(not b.get_active())))
        for control,signal in ((self.mode,'changed'),(self.shape,'changed'),(self.length,'value-changed'),(self.beats,'toggled')):control.connect(signal,self.edit)
        foot=Gtk.Box(spacing=12);self.status=label('');self.status.set_line_wrap(True);self.status.set_lines(3)
        foot.pack_start(self.status,True,True,0)
        self.preview_button=button('▶ '+text('Listen to transition','Послушать переход'),self.preview,'stage-accent');title.pack_end(self.preview_button,False,False,0)
        self.pack_start(foot,False,False,0)
        note=self.note=label(text(f'Recipes stay in Ember · {len(items)-1} loaded pairs. Preview starts the outro; manually queued songs stay queued.',
            f'Настройки сохраняются в Ember · загружено пар: {len(items)-1}. Прослушивание включит конец трека; ручная очередь сохранится.'))
        note.set_line_wrap(True);note.set_lines(2);self.pack_start(note,False,False,0)
        self.pairs.set_active(0);self.unsubscribe=service.subscribe(self.sync)
        self.connect('destroy',self.destroyed);self.show_all();self.sync()

    def resize(self,dense):
        self.dense=dense
        context=self.get_style_context()
        context.add_class('flow-desk-compact') if dense else context.remove_class('flow-desk-compact')
        self.set_spacing(5 if dense else 8);self.controls.set_spacing(8 if dense else 18)
        self.note.set_no_show_all(dense);self.note.set_visible(not dense)
        self.timeline.set_dense(dense);self.eq_panel.resize(dense);self.visuals()
        # Album thumbnails keep their original cached pixels; only allocation changes.
        for image in self.deck_images:
            original=getattr(image,'_flow_original',None) or image.get_pixbuf()
            if original:
                from gi.repository import GdkPixbuf
                image._flow_original=original;size=44 if dense else 60
                image.set_from_pixbuf(original.scale_simple(size,size,GdkPixbuf.InterpType.BILINEAR));image.set_size_request(size,size)

    def select_choice(self,combo,key):
        if self.updating:return
        if combo.get_active_id()==key:self.visuals()
        else:combo.set_active_id(key)

    def choose(self,*_):
        index=self.pairs.get_active()
        if index<0:return
        self.index=index;self.updating=True
        for image in self.deck_images:image._flow_original=None
        a,b=self.items[index:index+2]
        for n,item in enumerate((a,b)):
            self.artwork.load(self.deck_images[n],item.get('image',''),44 if getattr(self,'dense',False) else 60,10)
            self.deck_titles[n].set_text(item['title']);self.deck_artists[n].set_text(item.get('artist',''))
        value=self.flow.plans.get(self.key,a,b) or recipe({})
        self.mode.set_active_id(value['mode']);self.shape.set_active_id(value['shape']);self.length.set_value(value['seconds']);self.beats.set_active(value['beats'])
        self.eq_panel.set_plan(value,self.flow.eq_supported)
        self.timeline.cancel();self.timeline.set_plan(value,[a['title'],b['title']])
        self.updating=False;self.visuals()

    def value(self):return recipe(dict(mode=self.mode.get_active_id(),shape=self.shape.get_active_id(),seconds=self.length.get_value(),beats=self.beats.get_active(),**self.eq_panel.value()))

    def visuals(self):
        value=self.value();auto=value['mode']=='auto';cut=value['mode']=='cut'
        self.length.set_sensitive(not auto and not cut);self.shape.set_sensitive(not cut)
        self.knob.set_seconds(value['seconds'],not auto and not cut)
        self.updating=True
        for key,b in self.mode_buttons.items():b.set_active(key==value['mode'])
        for key,b in self.shape_buttons.items():b.set_active(key==value['shape']);b.set_sensitive(not cut)
        self.updating=False
        self.beats.set_sensitive(not cut and self.flow.beats_supported)
        self.length_label.set_text(text('AUTO · ≤8 s','АВТО · ≤8 с') if auto else '—' if cut else text(f'{value["seconds"]:g} s',f'{value["seconds"]:g} с'))
        self.timeline.set_plan(value)
        self.eq_panel.available=self.flow.eq_supported;self.eq_panel.sync()

    def timeline_changed(self,seconds,commit):
        self.updating=True;self.mode.set_active_id('manual');self.length.set_value(seconds);self.updating=False
        if commit:self.edit()
        else:self.visuals()

    def save(self,pairs):
        try:self.flow.plans.put(self.key,pairs)
        except (OSError,ValueError) as error:self.status.set_text(text('Could not save: ','Не удалось сохранить: ')+str(error));return False
        self.service.changed();return True

    def edit(self,*_):
        if self.updating:return
        self.visuals();a,b=self.items[self.index:self.index+2]
        if self.save([(a,b,self.value())]):self.sync()

    def automatic(self):
        value=recipe(dict(eq_mode='auto' if self.flow.eq_supported else 'off'))
        if self.save([(a,b,value) for a,b in zip(self.items,self.items[1:])]):
            self.choose();self.sync()

    def preview(self):
        if self.service.preview_transition(self.items,self.index):self.sync()

    def sync(self):
        if self.closed:return
        supported=self.flow.supported
        if self.eq_panel.available!=self.flow.eq_supported:
            self.eq_panel.available=self.flow.eq_supported;self.eq_panel.sync()
        preparing=bool(self.service.transition_preview)
        self.preview_button.set_sensitive(supported and not preparing)
        self.preview_button.set_label(text('Warming decks…','Готовим дорожки…') if preparing else '▶ '+text('Listen to transition','Послушать переход'))
        if not supported:message=text('Playback mixing requires in-player Apple Music or YouTube. These recipes stay saved.',
            'Для смешивания нужен встроенный Apple Music или YouTube. Настройки останутся сохранёнными.')
        elif self.service.transition_preview:message=text('Warming both decks for a real preview…','Готовим две дорожки для прослушивания…')
        elif not self.flow.enabled:message=text('Saved. Turn on the EmberFlow lamp to hear your transitions.',
            'Сохранено. Включи лампу EmberFlow, чтобы услышать переходы.')
        elif not self.flow.eq_supported:message=text('Saved · drag A or B to set overlap. Transition EQ currently requires Apple Music.',
            'Сохранено · двигай A или B для настройки сведения. Эквалайзер перехода пока доступен в Apple Music.')
        else:message=text('Saved · auto follows real silence and clear rhythm; native Lossless/Atmos uses smooth overlap without beat sync.',
            'Сохранено · Эмбер учитывает тишину и ясный ритм; в нативных Lossless/Atmos — плавное сведение без подгонки битов.')
        self.status.set_text(message)

    def destroyed(self,*_):
        self.closed=True
        if hasattr(self,'unsubscribe'):self.unsubscribe()
