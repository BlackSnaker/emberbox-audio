"""A quiet listening-scene selector; only cached status is read on GTK."""
import time
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib,Gdk,Pango
from source_picker import text
from scene_art import scene_frame

_style=None


def install_style():
    global _style
    if _style is not None:return
    _style=Gtk.CssProvider();_style.load_from_data(b'''
    .scene-popover { background-color: #292d24; color: #ebdbb2; border-radius: 25px;
      border: 1px solid rgba(235,219,178,.09); box-shadow: none; }
    .scene-control { color: #ebdbb2; }
    .scene-control .drawer-heading { font-size: 10px; letter-spacing: 2px; color: #b79b5c; }
    .scene-control .scene-title { color: #fbf1c7; font-size: 28px; font-weight: bold; letter-spacing: -.7px; }
    .scene-control .scene-subtitle { color: #bab795; font-size: 12px; }
    .scene-control button.scene-choice { font-size: 12px; padding: 11px 9px; border-radius: 14px;
      background-image: linear-gradient(to bottom right,#373d2f,#2b3226); color: #b6b294;
      border: 1px solid rgba(235,219,178,.04); box-shadow: 2px 3px 6px rgba(0,0,0,.18), inset 0 1px rgba(235,219,178,.04);
      outline-width: 0; transition: color 250ms ease, background-color 250ms ease; }
    .scene-control button.scene-choice:checked { color: #f4d18a; background-image: linear-gradient(to bottom,#414332,#303526);
      border-color: rgba(250,189,47,.22); box-shadow: inset 1px 2px 5px rgba(0,0,0,.22), 0 1px rgba(235,219,178,.04); }
    .scene-control checkbutton { color: #c1b99c; font-size: 11px; }
    .scene-control checkbutton check { background-image: linear-gradient(to bottom,#1d251a,#303928);
      border: 1px solid #65704e; border-radius: 5px; color: #f2c568; min-width: 14px; min-height: 14px; }
    .scene-control combobox button { color: #ddd0a9; background-image: linear-gradient(to bottom,#252c20,#22291d);
      border: 1px solid rgba(235,219,178,.06); border-radius: 12px; padding: 7px 10px; box-shadow: inset 1px 2px 4px rgba(0,0,0,.17); }
    .scene-control combobox { font-size: 12px; }
    .scene-control .caption { color: #a8a48a; font-size: 11px; }
    .scene-control .headphone-tuning label { color: #d5c8a5; font-size: 12px; }
    .scene-control .headphone-tuning .drawer-heading { color: #b79b5c; font-size: 10px; }
    .scene-control .headphone-tuning .caption { color: #a8a48a; font-size: 11px; }
    .scene-control expander title { color: #e8d7a9; padding: 4px 0; }
    .scene-control scale { padding: 6px 0; }
    .scene-control scale trough { background-image: linear-gradient(to bottom,#161e15,#242d1f);
      border: 1px solid rgba(235,219,178,.06); min-height: 4px; border-radius: 5px; }
    .scene-control scale highlight { background-image: linear-gradient(to right,#b57c27,#e3b965); border-radius: 5px; }
    .scene-control scale slider { background-image: linear-gradient(to bottom right,#f2d08a,#ba8d3c);
      border: 1px solid #e7bd65; min-width: 13px; min-height: 13px; border-radius: 50%;
      box-shadow: 0 2px 4px rgba(0,0,0,.3), inset 0 1px rgba(255,244,200,.4); }
    ''');Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),_style,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class ScenePreview(Gtk.Image):
    def __init__(self):
        super().__init__();self.value=self.target=0.;self.angle=self.target_angle=30.;self.opening=0.;self.tick=0
        self.connect('map',self.mapped);self.connect('unmap',self.settle);self.connect('destroy',self.settle)
    def set_scene(self,mode,angle):
        target=float(mode=='headphones')
        if target==self.target and angle==self.target_angle:return
        self.target=target;self.target_angle=float(angle)
        if self.get_mapped():self.animate()
        else:self.value=target;self.angle=float(angle);self.paint()
    def mapped(self,*_):
        self.opening=0.;self.animate()
    def animate(self):
        if not Gtk.Settings.get_default().get_property('gtk-enable-animations'):self.settle();return
        self.start=(self.value,self.angle,self.opening);self.elapsed=0.;self.last=None
        if not self.tick:self.tick=self.add_tick_callback(self.frame)
    def frame(self,*_):
        now=time.monotonic();self.elapsed+=min(.05,max(0.,now-self.last)) if self.last is not None else 0.;self.last=now
        t=min(1.,self.elapsed/.72);ease=t*t*t*(t*(t*6-15)+10)
        self.value=self.start[0]+(self.target-self.start[0])*ease;self.angle=self.start[1]+(self.target_angle-self.start[1])*ease
        self.opening=self.start[2]+(1-self.start[2])*ease;self.paint()
        if t>=1:self.tick=0;return False
        return True
    def paint(self):self.set_from_pixbuf(scene_frame(round(self.value*100),round(self.angle),round(self.opening*100)))
    def settle(self,*_):
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        self.value=self.target;self.angle=self.target_angle;self.opening=1.;self.paint()


class SceneControl(Gtk.Box):
    def __init__(self,apple):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=7)
        install_style()
        self.apple=apple;self.updating=False;self.key=None;self.pending=None
        self.get_style_context().add_class('scene-control');self.set_border_width(18)
        heading=Gtk.Label(label='EMBER / SOUNDSTAGE');heading.set_xalign(0)
        heading.get_style_context().add_class('drawer-heading');self.pack_start(heading,False,False,0)
        title=Gtk.Label(label=text('A place in the music.','Место внутри музыки.'));title.set_xalign(0);title.get_style_context().add_class('scene-title');self.pack_start(title,False,False,1)
        self.subtitle=Gtk.Label();self.subtitle.set_xalign(0);self.subtitle.get_style_context().add_class('scene-subtitle');self.pack_start(self.subtitle,False,False,1)
        self.diagram=ScenePreview()
        self.pack_start(self.diagram,False,False,0)
        self.buttons={};row=Gtk.Box(spacing=5);group=None
        for mode,name in [('speakers',text('Speaker pair','Колонки 2.0')),('headphones',text('Headphones','Наушники'))]:
            button=Gtk.RadioButton.new_with_label_from_widget(group,name);group=button;button.set_mode(False)
            button.set_has_tooltip(False);button.set_can_focus(True)
            button.get_style_context().add_class('filter-chip');button.get_style_context().add_class('scene-choice')
            button.connect('clicked',lambda _b,m=mode:self.select(m));self.buttons[mode]=button;row.pack_start(button,True,True,0)
        self.pack_start(row,False,False,0)
        self.auto=Gtk.CheckButton(label=text('Follow the output automatically','Автовыбор по устройству'))
        self.auto.set_has_tooltip(False);self.auto.connect('toggled',self.automatic);self.pack_start(self.auto,False,False,0)
        self.options=Gtk.ComboBoxText();self.options.set_has_tooltip(False);self.options.connect('changed',self.option)
        for cell in self.options.get_cells():cell.set_property('ellipsize',Pango.EllipsizeMode.END);cell.set_property('max-width-chars',32)
        self.pack_start(self.options,False,False,0)
        self.headphone_box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        actions=Gtk.Box(spacing=6)
        self.ab=Gtk.Button(label=text('KU100 ⇄ KEMAR','KU100 ⇄ KEMAR'));self.ab.set_has_tooltip(False);self.ab.get_style_context().add_class('scene-choice')
        self.ab.connect('clicked',lambda _b:self.request(self.scene().get('preference','auto'),hrtf=1-self.scene().get('hrtf',0),sofa=''))
        actions.pack_start(self.ab,True,True,0)
        self.import_button=Gtk.Button(label=text('Import SOFA…','Импорт SOFA…'));self.import_button.set_has_tooltip(False);self.import_button.get_style_context().add_class('scene-choice')
        self.import_button.connect('clicked',self.import_sofa);actions.pack_start(self.import_button,True,True,0)
        self.headphone_box.pack_start(actions,False,False,0)
        self.import_note=Gtk.Label();self.import_note.set_xalign(0);self.import_note.set_line_wrap(True);self.import_note.set_max_width_chars(43)
        self.import_note.get_style_context().add_class('caption');self.headphone_box.pack_start(self.import_note,False,False,0)
        from headphone_control import HeadphoneControl
        self.tuning=HeadphoneControl(lambda values:self.request(self.scene().get('preference','auto'),headphones=values))
        self.headphone_box.pack_start(self.tuning,False,False,3);self.pack_start(self.headphone_box,False,False,2)
        self.headphone_box.show_all();self.headphone_box.set_no_show_all(True);self.custom=None;self.importing=False;self.disposed=False
        self.caption=Gtk.Label();self.caption.set_xalign(0);self.caption.set_line_wrap(True);self.caption.set_max_width_chars(29)
        self.caption.get_style_context().add_class('caption');self.pack_start(self.caption,False,False,0)
        self.note=Gtk.Label(label=text('Native Apple audio. Head models shape Atmos; headphone EQ also works with stereo. Bluetooth quality depends on its codec.',
            'Нативный звук Apple. Модель головы формирует Atmos; EQ работает и со стерео. Качество Bluetooth зависит от кодека.'))
        self.note.set_xalign(0);self.note.set_line_wrap(True);self.note.set_max_width_chars(48)
        self.note.get_style_context().add_class('caption');self.pack_start(self.note,False,False,0)
        body=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=7);body.set_border_width(18)
        for child in self.get_children():self.remove(child);body.pack_start(child,False,False,0)
        self.set_border_width(0);self.scroll=Gtk.ScrolledWindow();self.scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_propagate_natural_height(True);self.scroll.set_min_content_width(396)
        display=Gdk.Display.get_default();monitor=display.get_primary_monitor() or display.get_monitor(0)
        self.scroll.set_max_content_height(max(300,min(760,monitor.get_workarea().height-100)))
        self.scroll.add(body);self.pack_start(self.scroll,True,True,0)
        self.refresh();self.timer=0;self.connect('map',self.mapped);self.connect('unmap',self.closed);self.connect('destroy',self.destroyed)

    def mapped(self,*_):
        self.refresh()
        if not self.timer:self.timer=GLib.timeout_add(500,self.refresh)

    def scene(self):
        actual=self.apple.state.get('spatial',{}).get('scene') or {}
        if self.pending:
            preview,expected,until=self.pending
            if time.monotonic()>=until or all((actual.get(k) or '' if k=='sofa' else actual.get(k))==v for k,v in expected.items()):self.pending=None
            else:return preview
        return actual
    def request(self,mode,**values):
        current=self.scene();preview={**current,**values,'preference':mode,'mode':current.get('mode','headphones') if mode=='auto' else mode,'changing':True}
        expected={'preference':mode,**values}
        if 'hrtf' in values and 'sofa' not in values:preview['sofa']='';expected['sofa']=''
        if mode!='auto':expected['mode']=mode
        self.pending=(preview,expected,time.monotonic()+2.5);self.key=None;self.refresh()
        self.apple.set_scene(mode,**values)
    def refresh(self):
        s=self.scene();key=tuple(str(s.get(k)) for k in ('mode','preference','angle','hrtf','sofa','headphones','headphoneStatus','device','bluetooth','codec','changing'))
        if key==self.key:return True
        self.key=key;self.updating=True;mode=s.get('mode','headphones')
        for name,button in self.buttons.items():button.set_active(name==mode)
        self.auto.set_active(s.get('preference','auto')=='auto')
        self.options.remove_all()
        if mode=='speakers':
            for value,name in [(20,text('Close pair · ±20°','Близко · ±20°')),(30,text('Standard · ±30°','Стандарт · ±30°')),(40,text('Wide pair · ±40°','Широко · ±40°'))]:self.options.append(str(value),name)
            self.options.set_active_id(str(s.get('angle',30)))
        else:
            self.options.append('0',text('Head model · KU100','Модель головы · KU100'));self.options.append('1',text('Head model · KEMAR','Модель головы · KEMAR'))
            from hrtf_store import profiles
            if self.custom is None:self.custom=profiles()
            for ident,name in self.custom:self.options.append(ident,name+' · SOFA')
            self.options.set_active_id(s.get('sofa') or str(s.get('hrtf',0)))
        self.headphone_box.set_visible(mode=='headphones')
        self.tuning.refresh(s.get('headphones'),s.get('headphoneStatus'))
        caption=s.get('device') or text('Choose your listening output','Выбери, через что слушаешь')
        if s.get('bluetooth'):caption+=' · Bluetooth'+(' / '+str(s.get('codec')).upper().replace('_',' ') if s.get('codec') else '')
        if s.get('changing'):caption+='\n'+text('Settling into the new scene…','Перестраиваем сцену…')
        self.caption.set_text(caption);self.subtitle.set_text(text('Two speakers. One shared space.','Две колонки. Одно пространство.') if mode=='speakers' else text('A whole scene, just for you.','Целая сцена — только для тебя.'))
        self.updating=False;self.diagram.set_scene(mode,s.get('angle',30));return True

    def select(self,mode):
        if not self.updating and self.buttons[mode].get_active():
            self.request(mode)
    def automatic(self,button):
        if not self.updating:self.request('auto' if button.get_active() else self.scene().get('mode','headphones'))
    def option(self,combo):
        if self.updating or combo.get_active_id() is None:return
        s=self.scene();key='angle' if s.get('mode')=='speakers' else 'hrtf'
        if key=='hrtf' and len(combo.get_active_id())==64:
            self.request(s.get('preference','auto'),sofa=combo.get_active_id());return
        self.request(s.get('preference','auto'),**{key:int(combo.get_active_id())})
    def import_sofa(self,*_):
        if self.importing or getattr(self,'import_dialog',None):return
        popover=self.get_ancestor(Gtk.Popover)
        if popover:popover.set_modal(False)
        chooser=Gtk.FileChooserNative.new(text('Personal head model · SOFA','Личная модель головы · SOFA'),self.get_toplevel(),Gtk.FileChooserAction.OPEN,
            text('Import','Загрузить'),text('Cancel','Отмена'))
        self.import_dialog=chooser;chooser.set_modal(True)
        file_filter=Gtk.FileFilter();file_filter.set_name('SOFA · ≤32 MB');file_filter.add_pattern('*.sofa');chooser.add_filter(file_filter)
        def selected(dialog,response):
            source=dialog.get_filename() if response==Gtk.ResponseType.ACCEPT else None;dialog.destroy()
            self.import_dialog=None
            if popover and not self.disposed:popover.set_modal(True)
            if not source or self.disposed:return
            self.importing=True;self.import_button.set_sensitive(False)
            self.import_note.set_text(text('Checking the model in a separate process…','Проверяем модель в отдельном процессе…'))
            import threading
            def work():
                from hrtf_store import import_sofa
                try:result=import_sofa(source);error=''
                except Exception as e:result=None;error=str(e)
                GLib.idle_add(self.import_done,result,error)
            threading.Thread(target=work,name='hrtf-import',daemon=True).start()
        chooser.connect('response',selected);chooser.show()
    def import_done(self,result,error):
        if self.disposed:return False
        self.importing=False;self.import_button.set_sensitive(True)
        if result:
            ident,name=result;self.custom=None;self.key=None
            self.import_note.set_text(text('Verified locally · ','Проверено локально · ')+name)
            if self.get_mapped():self.request(self.scene().get('preference','auto'),sofa=ident)
        else:
            messages={'SOFA_RUNTIME_REQUIRED':text('Enable the native audio runtime first.','Сначала подготовь нативный звуковой движок.'),
                'SOFA_SIZE_LIMIT':text('Choose a regular SOFA file up to 32 MB.','Выбери обычный SOFA-файл до 32 МБ.'),
                'SOFA_LIBRARY_FULL':text('The library holds up to 32 imported models.','В библиотеке может быть до 32 загруженных моделей.')}
            self.import_note.set_text(messages.get(error,text('This SOFA model is not compatible with the current renderer. The previous model is kept.',
                'Эта SOFA-модель несовместима с текущим рендером. Предыдущая модель сохранена.')))
        return False
    def destroyed(self,*_):
        if getattr(self,'import_dialog',None):self.import_dialog.destroy();self.import_dialog=None
        self.disposed=True;self.closed()
    def closed(self,*_):
        if self.timer:GLib.source_remove(self.timer);self.timer=0
