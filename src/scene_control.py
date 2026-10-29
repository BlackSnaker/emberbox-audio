"""A quiet listening-scene selector; only cached status is read on GTK."""
import time
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib,Gdk
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
        self.pack_start(self.options,False,False,0)
        self.caption=Gtk.Label();self.caption.set_xalign(0);self.caption.set_line_wrap(True);self.caption.set_max_width_chars(29)
        self.caption.get_style_context().add_class('caption');self.pack_start(self.caption,False,False,0)
        self.note=Gtk.Label(label=text('Atmos adapts to your output. Stereo recordings keep their original mix.',
            'Сцена Atmos под твой выход. Стереозаписи сохраняют исходный микс.'))
        self.note.set_xalign(0);self.note.set_line_wrap(True);self.note.set_max_width_chars(48)
        self.note.get_style_context().add_class('caption');self.pack_start(self.note,False,False,0)
        self.refresh();self.timer=0;self.connect('map',self.mapped);self.connect('unmap',self.closed);self.connect('destroy',self.closed)

    def mapped(self,*_):
        self.refresh()
        if not self.timer:self.timer=GLib.timeout_add(500,self.refresh)

    def scene(self):
        actual=self.apple.state.get('spatial',{}).get('scene') or {}
        if self.pending:
            preview,expected,until=self.pending
            if time.monotonic()>=until or all(actual.get(k)==v for k,v in expected.items()):self.pending=None
            else:return preview
        return actual
    def request(self,mode,**values):
        current=self.scene();preview={**current,**values,'preference':mode,'mode':current.get('mode','headphones') if mode=='auto' else mode,'changing':True}
        expected={'preference':mode,**values}
        if mode!='auto':expected['mode']=mode
        self.pending=(preview,expected,time.monotonic()+2.5);self.key=None;self.refresh()
        self.apple.set_scene(mode,**values)
    def refresh(self):
        s=self.scene();key=tuple(s.get(k) for k in ('mode','preference','angle','hrtf','device','bluetooth','codec','changing'))
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
            self.options.set_active_id(str(s.get('hrtf',0)))
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
        self.request(s.get('preference','auto'),**{key:int(combo.get_active_id())})
    def closed(self,*_):
        if self.timer:GLib.source_remove(self.timer);self.timer=0
