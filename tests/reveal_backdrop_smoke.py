"""Read real shader pixels: transitions must retain the selected room palette."""
import ctypes as C
import sys,time
from pathlib import Path
import gi
gi.require_version('Gtk','3.0');gi.require_version('GdkPixbuf','2.0')
from gi.repository import Gtk,GdkPixbuf,GLib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from reveal_gl import RevealGL

window=Gtk.Window();window.set_default_size(96,64)
area=Gtk.GLArea();area.set_required_version(3,2);area.set_use_es(False);area.set_has_alpha(True)
window.add(area);result=[]

def render(*_):
    if result:return True
    driver=None
    try:
        if area.get_error():raise RuntimeError(str(area.get_error()))
        driver=RevealGL(allow_software=True)
        read=driver.lib.glReadPixels;read.restype=None
        read.argtypes=[C.c_int,C.c_int,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_void_p]
        width,height=area.get_allocated_width(),area.get_allocated_height()
        driver.call('Viewport',0,0,width,height)
        blank=(1,1,bytes(4))
        for rgb in ((18,20,20),(12,16,21),(18,34,28),(180,20,30),(15,30,190)):
            background=GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,False,8,1,1)
            background.fill((rgb[0]<<24)|(rgb[1]<<16)|(rgb[2]<<8)|255)
            uploads=[];call=driver.call
            def counted(name,*args):
                if name=='TexImage2D':uploads.append(args)
                return call(name,*args)
            driver.call=counted
            for previous in (None,blank):
                for progress in (.3,.5,.8,.95):
                    driver.draw(width,height,(-100,-100,1,1),(0,0,1,1),(.26,.26,.24),progress,None,blank,previous,background)
                    driver.call('Finish')
                    pixel=(C.c_ubyte*4)();read(width-2,height-2,1,1,0x1908,0x1401,pixel)
                    assert pixel[3]>0
                    expected=[value*pixel[3]/255 for value in rgb]
                    assert max(abs(pixel[i]-expected[i]) for i in range(3))<=2,(rgb,progress,previous is not None,list(pixel),expected)
            # One backdrop upload; first use may also upload the two endpoint
            # scenes. Their caches and the backdrop cache survive later frames.
            assert len(uploads)<=3,('Backdrop was uploaded every frame',len(uploads))
            driver.call=call
        texture=driver.backdrop_texture
        driver.close();driver.close()
        is_texture=driver.lib.glIsTexture;is_texture.restype=C.c_ubyte;is_texture.argtypes=[C.c_uint]
        assert not is_texture(texture) and driver.backdrop_uploaded is None
        result.append(True)
    except Exception as error:result.append(error)
    finally:
        if driver:driver.close()
    return True

area.connect('render',render);window.show_all()
try:
    deadline=time.monotonic()+5;context=GLib.MainContext.default()
    while not result and time.monotonic()<deadline:
        for _ in range(3):
            if context.pending():context.iteration(False)
        time.sleep(.002)
    assert result and result[0] is True,result
    print('PASS selected-theme framebuffer colours through entrance and lyrics morph, cached backdrop upload and GPU cleanup')
finally:window.destroy()
