"""Fixed-size motion art: update a GL texture without reallocating GTK."""
from gi.repository import GdkPixbuf, GLib, Gtk
from PIL import Image, ImageDraw
from reveal_gl import RevealGL


class MotionSurface(Gtk.Overlay):
    def __init__(self):
        super().__init__()
        self.still=Gtk.Image();self.add(self.still)
        self.area=Gtk.GLArea();self.area.set_required_version(3,2)
        self.area.set_use_es(False);self.area.set_has_alpha(True);self.area.set_auto_render(False)
        self.area.set_halign(Gtk.Align.FILL);self.area.set_valign(Gtk.Align.FILL)
        self.area.set_no_show_all(True)
        self.add_overlay(self.area);self.set_overlay_pass_through(self.area,True)
        self.area.connect('render',self.render);self.area.connect('unrealize',self.release)
        self.driver=None;self.failed=False;self.pixels=None;self.size=380;self.radius=22
        self.set_halign(Gtk.Align.FILL);self.set_valign(Gtk.Align.FILL)
        self.resize(self.size)

    def warmup(self,allow_software=False):
        if self.driver or self.failed:return
        try:
            parents=[];widget=self.area
            while widget and not widget.get_realized():parents.append(widget);widget=widget.get_parent()
            for widget in reversed(parents):widget.realize()
            self.area.make_current()
            if self.area.get_error():raise RuntimeError('Motion GL context unavailable')
            self.driver=RevealGL(allow_software=allow_software)
        except (OSError,RuntimeError,AttributeError):
            self.failed=True

    def resize(self,size,radius=22):
        self.size,self.radius=size,radius
        self.set_size_request(size,size);self.still.set_size_request(size,size)
        if self.pixels and not self.driver:self.paint_fallback()

    def paint_fallback(self):
        pixels=self.pixels
        if not getattr(pixels,'_motion_rounded',True):
            size=pixels.get_width()
            image=Image.frombytes('RGBA',(size,size),pixels.get_pixels())
            mask=Image.new('L',(size,size))
            ImageDraw.Draw(mask).rounded_rectangle((0,0,size-1,size-1),self.radius*size/self.size,fill=255)
            image.putalpha(mask)
            pixels=GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(image.tobytes()),GdkPixbuf.Colorspace.RGB,True,8,size,size,size*4)
        if pixels.get_width()!=self.size:
            pixels=pixels.scale_simple(self.size,self.size,GdkPixbuf.InterpType.BILINEAR)
        self.still.set_from_pixbuf(pixels);self.still.show();self.area.hide()

    def set_from_pixbuf(self,pixels):
        self.pixels=pixels
        if self.driver:
            self.still.hide();self.area.show();self.area.queue_render()
        else:self.paint_fallback()

    def render(self,_area,_context):
        if not self.driver or self.pixels is None:return True
        try:self.driver.draw_cover(self.area.get_allocated_width(),self.area.get_allocated_height(),self.pixels,self.radius)
        except (OSError,RuntimeError,AttributeError):
            self.release(self.area);self.failed=True;self.paint_fallback()
        return True

    def get_pixbuf(self):return self.pixels

    def clear(self):
        self.pixels=None;self.still.clear();self.area.hide()
        if self.driver:self.driver.uploaded=None

    def release(self,_area):
        if self.driver:
            self.area.make_current()
            if not self.area.get_error():self.driver.close()
            self.driver=None
