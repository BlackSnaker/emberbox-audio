"""A two-deck EQ drawer. Cut knobs automate the handover, never the master."""
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk
from source_picker import text
from flow_hardware import CutDial
from flow_plans import configuration


class EQPanel(Gtk.Box):
    def __init__(self,changed):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=9)
        self.changed=changed;self.updating=False;self.mode='off';self.out=[0.,0.,0.];self.incoming=[0.,0.,0.]
        self.available=False;self.dials=[];self.values=[];self.mode_buttons={}
        self.get_style_context().add_class('flow-instrument')
        top=Gtk.Box(spacing=10)
        self.toggle=Gtk.ToggleButton(label=text('Transition EQ','Эквалайзер перехода')+'  ▾')
        self.toggle.get_style_context().add_class('flow-selector');self.toggle.set_has_tooltip(False)
        top.pack_start(self.toggle,False,False,0)
        for key,en,ru in (('off','Direct','Прямой'),('auto','Ember · bass handover','Эмбер · передача баса'),('manual','By hand','Вручную')):
            b=Gtk.ToggleButton(label=text(en,ru));b.get_style_context().add_class('flow-selector');b.set_has_tooltip(False)
            b.connect('clicked',lambda _b,k=key:self.select(k));self.mode_buttons[key]=b;top.pack_start(b,True,True,0)
        self.pack_start(top,False,False,0)
        self.reveal=Gtk.Revealer();self.reveal.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN);self.reveal.set_transition_duration(300)
        self.toggle.connect('toggled',lambda b:self.reveal.set_reveal_child(b.get_active()))
        self.pack_start(self.reveal,False,False,0)
        content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=7);decks=Gtk.Box(spacing=20);decks.set_homogeneous(True)
        for lane,en,ru in ((0,'A · OUTGOING','A · УХОДЯЩИЙ'),(1,'B · INCOMING','B · СЛЕДУЮЩИЙ')):
            section=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4)
            heading=Gtk.Label(label=text(en,ru));heading.get_style_context().add_class('flow-engraving');heading.set_xalign(0);section.pack_start(heading,False,False,0)
            row=Gtk.Box(spacing=22);row.set_halign(Gtk.Align.CENTER)
            for band,en,ru in ((0,'LOW','НИЗКИЕ'),(1,'MID','СРЕДНИЕ'),(2,'HIGH','ВЫСОКИЕ')):
                cell=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3)
                name=Gtk.Label(label=text(en,ru));name.get_style_context().add_class('flow-engraving');cell.pack_start(name,False,False,0)
                dial=CutDial(lambda db,l=lane,b=band:self.adjust(l,b,db),text(en,ru)+' '+('A' if lane==0 else 'B'))
                dial.small=True;dial.frame=None;dial._render()
                cell.pack_start(dial,False,False,0);value=Gtk.Label();value.get_style_context().add_class('flow-time-display')
                cell.pack_start(value,False,False,0);row.pack_start(cell,False,False,0);self.dials.append(dial);self.values.append(value)
            section.pack_start(row,False,False,0);decks.pack_start(section,True,True,0)
        content.pack_start(decks,False,False,0)
        note=Gtk.Label(label=text('0…−12 dB · cuts unfold during the blend, then release to the original tone. Peak headroom is reserved.',
            '0…−12 дБ · ослабление разворачивается во время сведения и мягко отпускает исходный тембр. С запасом по пикам.'))
        note.get_style_context().add_class('stage-library-note');note.set_line_wrap(True);note.set_max_width_chars(85);note.set_xalign(0)
        content.pack_start(note,False,False,0);self.reveal.add(content)

    def set_plan(self,plan,available):
        self.mode=plan['eq_mode'];self.out=list(plan['eq_out']);self.incoming=list(plan['eq_in']);self.available=available;self.sync()

    def value(self):return dict(eq_mode=self.mode,eq_out=list(self.out),eq_in=list(self.incoming))

    def select(self,key):
        if self.updating:return
        if key=='manual' and self.mode=='auto':
            preset=configuration(dict(eq_mode='auto'));self.out=preset['out'];self.incoming=preset['in']
        self.mode=key
        if key=='manual':self.toggle.set_active(True)
        self.sync();self.changed()

    def adjust(self,lane,band,db):
        if self.updating:return
        if self.mode=='auto':
            preset=configuration(dict(eq_mode='auto'));self.out=preset['out'];self.incoming=preset['in']
        self.mode='manual';(self.out if lane==0 else self.incoming)[band]=db
        self.sync();self.changed()

    def sync(self):
        self.updating=True
        for key,b in self.mode_buttons.items():b.set_active(self.mode==key);b.set_sensitive(self.available or key=='off')
        plan=dict(self.value());active=configuration(plan)
        levels=(active['out']+active['in']) if active else [0]*6
        for i,(dial,label) in enumerate(zip(self.dials,self.values)):
            dial.set_db(levels[i],self.available and self.mode!='off');label.set_text(f'{levels[i]:g} '+text('dB','дБ'))
        self.updating=False

    def resize(self,dense):
        for dial in self.dials:
            if not dial.small:dial.small=True;dial.frame=None;dial._render()
