"""Headphone voicing, with an honest measurement label and matched dry A/B."""
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib,Pango
from headphone_profiles import catalogue,settings,profile
from source_picker import text


class HeadphoneControl(Gtk.Box):
    def __init__(self,changed):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        self.changed=changed;self.updating=False;self.timer=0;self.value=settings();self.key=None
        self.get_style_context().add_class('headphone-tuning')
        label=Gtk.Label(label=text('YOUR HEADPHONES','ТВОИ НАУШНИКИ'));label.set_xalign(0)
        label.get_style_context().add_class('drawer-heading');self.pack_start(label,False,False,0)
        self.model=Gtk.ComboBoxText();self.model.set_has_tooltip(False)
        for p in catalogue():
            name=text('Original · no correction','Исходный звук · без коррекции') if p['id']=='none' else p['name']
            if p['id']=='buds4-pro':name+=text(' · original',' · исходный звук')
            self.model.append(p['id'],name)
        for cell in self.model.get_cells():cell.set_property('ellipsize',Pango.EllipsizeMode.END);cell.set_property('max-width-chars',33)
        self.model.connect('changed',self.edited);self.pack_start(self.model,False,False,0)
        self.evidence=Gtk.Label();self.evidence.set_xalign(0);self.evidence.set_line_wrap(True);self.evidence.set_max_width_chars(43)
        self.evidence.get_style_context().add_class('caption');self.pack_start(self.evidence,False,False,0)
        self.expander=Gtk.Expander(label=text('Fine tuning','Тонкая настройка'));self.expander.set_has_tooltip(False)
        self.pack_start(self.expander,False,False,0)
        inner=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=7);inner.set_margin_top(10);self.expander.add(inner)
        self.scales={};self.labels={}
        for key,title,lo,hi,unit in [('strength',text('Correction','Коррекция'),0,100,'%'),('bass',text('Bass','Низкие частоты'),-4,4,' dB'),
                                    ('treble',text('Air','Высокие частоты'),-4,4,' dB'),('balance',text('L / R balance','Баланс L / R'),-20,20,'')]:
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=2);row=Gtk.Box()
            name=Gtk.Label(label=title);name.set_xalign(0);row.pack_start(name,True,True,0)
            value=Gtk.Label();self.labels[key]=(value,unit);row.pack_end(value,False,False,0);box.pack_start(row,False,False,0)
            scale=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,lo,hi,1);scale.set_draw_value(False);scale.set_has_tooltip(False)
            if lo<0:scale.add_mark(0,Gtk.PositionType.BOTTOM,None)
            scale.connect('value-changed',self.edited);self.scales[key]=scale;box.pack_start(scale,False,False,0);inner.pack_start(box,False,False,0)
        self.compare=Gtk.ToggleButton(label=text('A / B · Original','A / B · Исходный звук'))
        self.compare.get_style_context().add_class('scene-choice');self.compare.set_has_tooltip(False)
        self.compare.connect('toggled',self.edited);inner.pack_start(self.compare,False,False,2)
        note=Gtk.Label(label=text('A/B keeps the same headroom. Head models remain independent.','A/B сохраняет запас по громкости. Модель головы выбирается отдельно.'))
        note.set_xalign(0);note.set_line_wrap(True);note.set_max_width_chars(43);note.get_style_context().add_class('caption');inner.pack_start(note,False,False,0)
        reset=Gtk.Button(label=text('Reset tuning','Сбросить настройку'));reset.set_has_tooltip(False);reset.get_style_context().add_class('scene-choice')
        reset.connect('clicked',lambda _b:self.reset());inner.pack_start(reset,False,False,0)
        self.status=Gtk.Label();self.status.set_xalign(0);self.status.set_line_wrap(True);self.status.set_max_width_chars(43)
        self.status.get_style_context().add_class('caption');inner.pack_start(self.status,False,False,0)
        self.connect('unmap',self.closed);self.connect('destroy',self.closed)
        self.refresh({},None)

    def refresh(self,value,status):
        v=settings(value);key=(tuple(v.items()),str(status))
        if key==self.key or self.timer:return
        self.key=key;self.value=v;self.updating=True
        self.model.set_active_id(v['profile']);self.compare.set_active(v['bypass'])
        for k,scale in self.scales.items():scale.set_value(v[k])
        p=profile(v['profile']);self.scales['strength'].set_sensitive(bool(p['filters']))
        self.evidence.set_text(text('Measured correction · RTINGS / AutoEq. Use the factory EQ setting.',
            'Коррекция по измерениям · RTINGS / AutoEq. Используй заводскую настройку EQ.') if p.get('measured') else
            text('No measured correction is applied. Bass, air and balance are available below.',
            'Измеренная коррекция не применяется. Ниже доступны низкие, высокие и баланс.'))
        if status and status.get('error'):message=text('DSP needs SciPy. Re-run the installer with --apple-atmos. Playback stays available.',
            'Для DSP нужен SciPy. Повтори установку с --apple-atmos. Воспроизведение доступно.')
        elif status and status.get('active'):message=text('Float64 EQ · linked peak protection · headroom ',
            'EQ Float64 · общая защита пиков · запас ')+str(status.get('headroomDb',0))+' dB'
        else:message=text('Native Apple playback · tuning is saved for this output.','Нативный звук Apple · настройка сохраняется для этого выхода.')
        self.status.set_text(message);self.updating=False;self.values()

    def values(self):
        for k,(label,unit) in self.labels.items():
            n=round(self.scales[k].get_value());label.set_text(('+' if n>0 and k in ('bass','treble') else '')+str(n)+unit)

    def edited(self,*_):
        if self.updating:return
        self.values()
        if self.timer:GLib.source_remove(self.timer)
        self.timer=GLib.timeout_add(140,self.flush)

    def flush(self):
        self.timer=0
        self.value=settings({'profile':self.model.get_active_id() or 'none','bypass':self.compare.get_active(),
                             **{k:round(s.get_value()) for k,s in self.scales.items()}})
        self.key=None;self.changed(self.value);return False

    def reset(self):
        if self.timer:GLib.source_remove(self.timer);self.timer=0
        self.refresh(settings(),None);self.changed(settings())

    def closed(self,*_):
        if self.timer:GLib.source_remove(self.timer);self.timer=0;self.flush()
