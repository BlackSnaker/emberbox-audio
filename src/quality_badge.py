"""Small, warm quality badge; details open by click, never on hover."""
from gi.repository import Gtk
from source_picker import text
from audio_quality import current

CSS=b'''
button.ember-quality { background-image: linear-gradient(to bottom right,rgba(81,77,48,.48),rgba(38,43,31,.64));
  background-color: transparent; border: 1px solid rgba(215,153,33,.15); border-radius: 10px;
  color: #d7bd80; padding: 3px 8px; min-height: 0; min-width: 0; font-size: 9px;
  box-shadow: inset 0 1px rgba(255,241,206,.035); outline-width: 0; }
button.ember-quality:hover { border-color: rgba(250,189,47,.36); color: #ebdbb2; }
button.ember-quality:focus { outline-width: 0; outline-style: none; }
.ember-quality-popover { background-color: #282b24; border: 1px solid rgba(189,174,147,.15); border-radius: 17px; color: #ebdbb2; }
.ember-quality-heading { color: #b5a16e; font-size: 9px; letter-spacing: 1px; }
.ember-quality-name { color: #f3d48a; font-size: 17px; font-weight: bold; }
.ember-quality-detail { color: #d3c7a5; font-size: 11px; }
.ember-quality-note { color: #a89984; font-size: 10px; }
'''


class QualityBadge(Gtk.Button):
    def __init__(self):
        super().__init__()
        self.get_style_context().add_class('ember-quality')
        self.set_halign(Gtk.Align.START);self.set_valign(Gtk.Align.CENTER)
        self.set_has_tooltip(False);self.set_no_show_all(True)
        self.get_accessible().set_name(text('Audio quality · details','Качество звука · подробнее'))
        self.model=None;self.popover=None
        self.connect('clicked',self.open_details)
        self.connect('destroy',lambda *_:self.popover.destroy() if self.popover else None)

    def update(self,host):
        model=current(host)
        self.set_visible(bool(getattr(host,'length',0)))
        if model==self.model:return
        self.model=model;self.set_label('≋  '+model['badge'])
        if self.popover:self.populate()

    def open_details(self,_button=None):
        if self.popover and self.popover.get_visible():self.popover.popdown();return
        if not self.popover:
            self.popover=Gtk.Popover.new(self);self.popover.get_style_context().add_class('ember-quality-popover')
        self.populate();self.popover.popup()

    def populate(self):
        child=self.popover.get_child()
        if child:child.destroy()
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=9);box.set_border_width(17)
        box.set_size_request(280,-1);self.popover.add(box)
        def line(value,style):
            item=Gtk.Label(label=value);item.set_xalign(0);item.set_line_wrap(True);item.set_max_width_chars(37)
            item.get_style_context().add_class(style);box.pack_start(item,False,False,0)
        model=self.model or current(None)
        line(text('PLAYING FORMAT','ФОРМАТ ВОСПРОИЗВЕДЕНИЯ'),'ember-quality-heading')
        line(model['name'] or text('Not reported','Не передаётся'),'ember-quality-name')
        line(model['details'] or text('This source does not report the stream format.','Источник не сообщает формат аудиопотока.'),'ember-quality-detail')
        if model['known']:line(text('Stream before system audio processing.','Поток до обработки звуковой системой.'),'ember-quality-note')
        if model['policy']:
            line(text('QUALITY PREFERENCE','ПРИОРИТЕТ КАЧЕСТВА'),'ember-quality-heading')
            line(model['policy'],'ember-quality-note')
        if model['available']:
            separator=Gtk.Separator();separator.set_margin_top(5);separator.set_margin_bottom(5);box.pack_start(separator,False,False,0)
            line(text('AVAILABLE IN THE CATALOGUE','ДОСТУПНО В КАТАЛОГЕ'),'ember-quality-heading')
            line(' · '.join(model['available']),'ember-quality-detail')
            line(text('Available formats may differ from current playback.','Доступные форматы могут отличаться от текущего воспроизведения.'),'ember-quality-note')
        box.show_all()
