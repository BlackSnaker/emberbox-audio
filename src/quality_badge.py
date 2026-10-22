"""Warm frosted-glass quality badge; details open by click, never on hover."""
import math
import random
from PIL import Image,ImageFilter,ImageDraw
from gi.repository import Gtk,Gdk,GdkPixbuf,GLib
from source_picker import text
from audio_quality import current

CSS=b'''
button.ember-quality { background-image: linear-gradient(165deg,rgba(239,232,205,.20),rgba(185,194,170,.10) 48%,rgba(132,143,123,.16));
  background-color: rgba(175,184,160,.06); border: 1px solid rgba(246,239,211,.24); border-radius: 10px;
  color: #e8dfbe; padding: 3px 8px; min-height: 0; min-width: 0; font-size: 9px;
  box-shadow: inset 0 1px rgba(255,249,224,.17), inset 0 -1px rgba(20,29,21,.12); outline-width: 0; }
button.ember-quality:hover { border-color: rgba(255,242,198,.42); color: #fbf1d1;
  background-image: linear-gradient(165deg,rgba(248,238,204,.25),rgba(198,204,178,.14) 48%,rgba(155,164,139,.20)); }
button.ember-quality:focus { outline-width: 0; outline-style: none; }
.ember-quality-popover { background-color: rgba(73,79,67,.90); background-image: none;
  border: 1px solid rgba(246,240,214,.27); border-radius: 19px; padding: 0;
  box-shadow: 0 6px 20px rgba(8,15,10,.15); color: #eee5ca; }
.ember-quality-heading { color: #d6cbab; font-size: 9px; letter-spacing: 1px; }
.ember-quality-name { color: #fff0c4; font-size: 17px; font-weight: bold; }
.ember-quality-detail { color: #eee5ca; font-size: 11px; }
.ember-quality-note { color: #c4bfa9; font-size: 10px; }
.ember-quality-popover separator { background-color: rgba(242,235,208,.13); min-height: 1px; }
'''


class FrostedPanel(Gtk.Overlay):
    """One blurred snapshot of our own window per opening; no live capture loop."""
    grain=None

    def __init__(self):
        super().__init__()
        self.backdrop=None;self.host=None;self.scale=(1.,1.);self.render_key=None;self.content=None
        self.image=Gtk.Image();self.add(self.image)
        self.connect('size-allocate',lambda *_:self.render())
        self.connect('map',lambda *_:self.render())
        if FrostedPanel.grain is None:
            rng=random.Random(19);pixels=bytearray()
            for _ in range(64*64):
                light=rng.randrange(256);pixels.extend((light,light,light,6))
            FrostedPanel.grain=Image.frombytes('RGBA',(64,64),bytes(pixels))

    def set_content(self,box):
        if self.content:self.content.destroy()
        self.content=box;self.add_overlay(box);box.show_all()
        size=box.get_preferred_size()[1]
        self.image.clear()
        self.image.set_size_request(size.width,size.height)
        self.render_key=None;self.show_all()
        GLib.idle_add(self.render)

    def prepare(self,host):
        self.backdrop=None;self.host=host;self.render_key=None
        native=host.get_window() if isinstance(host,Gtk.Window) else None
        if native:
            try:
                width,height=native.get_width(),native.get_height()
                pixels=Gdk.pixbuf_get_from_window(native,0,0,width,height)
                if pixels:
                    mode='RGBA' if pixels.get_has_alpha() else 'RGB'
                    image=Image.frombytes(mode,(width,height),bytes(pixels.get_pixels()),'raw',mode,pixels.get_rowstride())
                    small=(max(1,math.ceil(width/5)),max(1,math.ceil(height/5)))
                    self.backdrop=image.resize(small,Image.Resampling.BOX).filter(ImageFilter.GaussianBlur(4)).convert('RGBA')
                    self.scale=(width/small[0],height/small[1])
            except (GLib.Error,OSError,ValueError,TypeError):pass
        self.render()

    def render(self):
        width,height=self.get_allocated_width(),self.get_allocated_height()
        if min(width,height)<2:return
        point=self.translate_coordinates(self.host,0,0) if self.host else None
        x,y=point or (0,0);key=(width,height,x,y,id(self.backdrop))
        if key==self.render_key:return
        self.render_key=key
        if self.backdrop and point:
            sx,sy=self.scale
            image=self.backdrop.transform((width,height),Image.Transform.AFFINE,
                (1/sx,0,x/sx,0,1/sy,y/sy),Image.Resampling.BILINEAR,fillcolor=(47,54,46,255))
        else:image=Image.new('RGBA',(width,height),(40,48,40,255))
        # Milk-coloured condensation and a fading upper reflection.
        wash=Image.new('RGBA',(1,height));rows=[]
        for row in range(height):
            t=row/max(1,height-1);shine=max(0,1-t/.42)*.07
            rows.append((round((.38-.16*t+shine)*255),round((.40-.14*t+shine)*255),
                         round((.34-.12*t+shine)*255),round((.78+.07*t)*255)))
        wash.putdata(rows);image=Image.alpha_composite(image,wash.resize((width,height)))
        grain=Image.new('RGBA',(width,height))
        for gy in range(0,height,64):
            for gx in range(0,width,64):grain.paste(self.grain,(gx,gy))
        image=Image.alpha_composite(image,grain)
        edge=Image.new('RGBA',(width,height))
        ImageDraw.Draw(edge).rounded_rectangle((0,0,width-1,height-1),radius=17,outline=(247,240,215,35),width=1)
        image=Image.alpha_composite(image,edge)
        mask=Image.new('L',(width,height));ImageDraw.Draw(mask).rounded_rectangle((0,0,width-1,height-1),radius=17,fill=255)
        image.putalpha(mask)
        pixels=GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(image.tobytes()),GdkPixbuf.Colorspace.RGB,True,8,width,height,width*4)
        self.image.set_from_pixbuf(pixels)


class QualityBadge(Gtk.Button):
    def __init__(self):
        super().__init__()
        self.get_style_context().add_class('ember-quality')
        self.set_halign(Gtk.Align.START);self.set_valign(Gtk.Align.CENTER)
        self.set_has_tooltip(False);self.set_no_show_all(True)
        self.get_accessible().set_name(text('Audio quality · details','Качество звука · подробнее'))
        self.model=None;self.popover=None;self.panel=None
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
            self.panel=FrostedPanel();self.popover.add(self.panel)
            self.popover.connect('closed',lambda *_:setattr(self.panel,'backdrop',None))
        self.populate();self.panel.prepare(self.get_toplevel());self.popover.popup()

    def populate(self):
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=9);box.set_border_width(17)
        box.set_size_request(280,-1)
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
        self.panel.set_content(box)
