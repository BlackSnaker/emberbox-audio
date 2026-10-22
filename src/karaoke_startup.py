"""A small, nonblocking welcome while the real audio helper prepares karaoke."""
import math

from gi.repository import Gtk
from source_picker import text

CSS=b'''
.karaoke-warm-title { color: #f4d18a; font-size: 34px; font-weight: bold; letter-spacing: -.5px; }
.karaoke-warm-note { color: #bdae93; font-size: 13px; }
.karaoke-warm-hint { color: #858773; font-size: 10px; }
.karaoke-ember { color: #f2b64d; font-size: 13px; }
.karaoke-warm-progress { padding: 0; }
.karaoke-warm-progress trough { min-height: 3px; border: none; border-radius: 3px;
  background-color: rgba(235,219,178,.055); box-shadow: none; }
.karaoke-warm-progress progress { min-height: 3px; border: none; border-radius: 3px;
  background-image: linear-gradient(to right,#a87532,#f8cd70,#b98942); box-shadow: none; }
.ember-stage .small-screen .karaoke-warm-title { font-size: 25px; }
'''


def label(value,style):
    result=Gtk.Label(label=value);result.get_style_context().add_class(style)
    result.set_has_tooltip(False)
    return result


class KaraokeStartup(Gtk.Box):
    """No timer or audio command: the parent's existing frame clock advances it.

    Indeterminate motion means waiting, never a guessed percentage. Only the
    first processed-audio notification may produce the ready state.
    """
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=18)
        self.set_valign(Gtk.Align.CENTER);self.set_halign(Gtk.Align.CENTER)
        self.state='idle';self.last_pulse=None;self.dot_levels=None
        embers=self.embers=Gtk.Box(spacing=14);embers.set_halign(Gtk.Align.CENTER)
        self.dots=[label('●','karaoke-ember') for _ in range(3)]
        for dot in self.dots:embers.pack_start(dot,False,False,0)
        self.pack_start(embers,False,False,0)
        self.title=label(text('Let the sound warm up','Дадим звуку согреться'),'karaoke-warm-title')
        self.pack_start(self.title,False,False,0)
        self.note=label('','karaoke-warm-note');self.note.set_line_wrap(True)
        self.note.set_justify(Gtk.Justification.CENTER);self.note.set_max_width_chars(58)
        self.note.set_size_request(-1,40);self.pack_start(self.note,False,False,0)
        self.progress=Gtk.ProgressBar();self.progress.set_show_text(False)
        self.progress.set_size_request(280,3);self.progress.set_halign(Gtk.Align.CENTER)
        self.progress.set_pulse_step(.035)
        self.progress.get_style_context().add_class('karaoke-warm-progress')
        self.progress.get_accessible().set_name(text('Connecting karaoke','Подключение караоке'))
        self.pack_start(self.progress,False,False,2)
        self.hint=label(text('You can switch it off at any time','Тумблер можно выключить в любой момент'),'karaoke-warm-hint')
        self.pack_start(self.hint,False,False,0)

    @property
    def waiting(self):return self.state in ('model','buffering')

    def set_small(self,small):
        self.set_spacing(4 if small else 18)
        self.note.set_size_request(-1,18 if small else 40)
        self.hint.set_no_show_all(small);self.hint.set_visible(not small)
        self.embers.set_no_show_all(small);self.embers.set_visible(not small)

    def sync(self,starting,active,phase='',error=''):
        was_waiting=self.waiting
        if error or not (starting or active):state='idle'
        elif starting:state='buffering' if phase=='buffering' else 'model'
        elif self.waiting:state='ready'
        else:return
        if state==self.state:return
        self.state=state
        if state=='idle':
            self.last_pulse=None;self.progress.set_fraction(0.);return
        if state=='ready':
            self.title.set_text(text('Your moment to sing','Можно петь'))
            self.note.set_text(text('Karaoke is ready','Караоке готово'))
            self.progress.set_fraction(1.)
            for dot in self.dots:dot.set_opacity(1.)
            self.dot_levels=None;return
        self.title.set_text(text('Let the sound warm up','Дадим звуку согреться'))
        self.note.set_text(text('A short pause — your music will return in a moment',
                                'Короткая пауза — музыка сейчас вернётся') if state=='buffering' else
                           text('Preparing karaoke. The music may briefly become quiet',
                                'Готовим караоке. Музыка может ненадолго затихнуть'))
        if not was_waiting:
            self.progress.set_fraction(0.)
            if self.get_settings().get_property('gtk-enable-animations'):self.progress.pulse()
            self.last_pulse=None

    def advance(self,now):
        if not self.waiting:return False
        if not self.get_settings().get_property('gtk-enable-animations'):return True
        if self.last_pulse is None or now-self.last_pulse>=.1:
            self.progress.pulse();self.last_pulse=now
        levels=tuple(round((.33+.67*(.5+.5*math.sin(now*math.tau/1.65-index*.85)))*50)/50 for index in range(3))
        if levels!=self.dot_levels:
            for dot,level in zip(self.dots,levels):dot.set_opacity(level)
            self.dot_levels=levels
        return True

    def cancel(self):self.sync(False,False)
