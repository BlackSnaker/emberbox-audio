"""GPU panorama: upload one immutable mirror texture, move only a uniform.

Uses the existing system-GL bridge. No Python GL package, frame readback,
frame-sized allocation or per-frame texture upload is required.
"""
import ctypes as C
import os
import subprocess
import sys
from functools import lru_cache
from reveal_gl import RevealGL


@lru_cache(maxsize=1)
def hardware_available():
    """Probe outside the application, before GTK chooses its room paint path.

    Merely creating an unaccelerated GL context can make some GTK displays
    composite all future Cairo frames through software GL. A short-lived,
    unmapped child process avoids changing the application's display state.
    The theme worker calls this before handing its material back to GTK.
    """
    if os.environ.get('LIBGL_ALWAYS_SOFTWARE','').lower() in ('1','true','yes'):return False
    code = r'''import ctypes as C,sys
from ctypes.util import find_library
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk
try:
    window=Gtk.Window();area=Gtk.GLArea()
    area.set_required_version(3,2);area.set_use_es(False);window.add(area)
    window.realize();area.realize();area.make_current()
    if area.get_error():sys.exit(2)
    lib=C.CDLL(find_library('GL'));query=lib.glGetString
    query.restype=C.c_char_p;query.argtypes=[C.c_uint]
    name=(query(0x1F01) or b'').decode(errors='replace').lower()
    if not name:sys.exit(2)
    sys.exit(1 if any(token in name for token in ('llvmpipe','softpipe','swrast','software rasterizer')) else 0)
except Exception:sys.exit(2)
'''
    try:
        result=subprocess.run([sys.executable,'-c',code],stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3,check=False)
        return {0:True,1:False}.get(result.returncode)
    except (OSError,subprocess.TimeoutExpired):return None


FRAGMENT=b'''#version 150
in vec2 uv;
out vec4 color;
uniform sampler2D cover;
uniform float drift;
void main(){
  vec2 p=uv*2.0-1.0;
  float mask=smoothstep(.50,.98,abs(p.x));
  if(mask<.00001){color=vec4(0);return;}
  color=texture(cover,vec2(uv.x-drift,uv.y))*mask;
}'''


class MirrorPanGL(RevealGL):
    def __init__(self,allow_software=False):
        super().__init__(allow_software,fragment=FRAGMENT,uniforms=('drift',))
        self.atlas=None
        for name,result,args in (
                ('GetIntegerv',None,(C.c_uint,C.POINTER(C.c_int))),
                ('IsEnabled',C.c_ubyte,(C.c_uint,)),('Enable',None,(C.c_uint,)),
                ('BindBuffer',None,(C.c_uint,C.c_uint))):
            call=getattr(self.lib,'gl'+name);call.restype=result;call.argtypes=args;self.functions[name]=call

    def integer(self,name):
        value=C.c_int();self.call('GetIntegerv',name,C.byref(value));return value.value

    def draw(self,width,height,atlas,drift):
        program=self.integer(0x8B8D);vao=self.integer(0x85B5);active=self.integer(0x84E0)
        blend=bool(self.call('IsEnabled',0x0BE2))
        viewport=(C.c_int*4)();self.call('GetIntegerv',0x0BA2,viewport)
        unpack={key:self.integer(key) for key in (0x0CF5,0x0CF2,0x0CF3,0x0CF4)}
        buffer=self.integer(0x88EF)
        self.call('ActiveTexture',0x84C0);binding=self.integer(0x8069)
        try:
            self.call('Disable',0x0BE2);self.call('Viewport',0,0,width,height)
            self.call('UseProgram',self.program);self.call('BindVertexArray',self.vao)
            self.call('BindBuffer',0x88EC,0);self.call('PixelStorei',0x0CF3,0);self.call('PixelStorei',0x0CF4,0)
            if atlas is not self.atlas:
                w,h,frames=atlas;self.raw_texture(self.texture,(w,h,frames[0]))
                self.call('TexParameteri',0x0DE1,0x2802,0x2901) # GL_REPEAT along the panorama.
                self.atlas=atlas
            self.call('BindTexture',0x0DE1,self.texture)
            self.call('Uniform1i',self.uniforms['cover'],0)
            self.call('Uniform1f',self.uniforms['drift'],float(drift))
            self.call('DrawArrays',0x0004,0,3)
        finally:
            self.call('BindVertexArray',vao);self.call('UseProgram',program)
            self.call('BindTexture',0x0DE1,binding);self.call('ActiveTexture',active)
            for key,value in unpack.items():self.call('PixelStorei',key,value)
            self.call('BindBuffer',0x88EC,buffer);self.call('Viewport',*viewport)
            if blend:self.call('Enable',0x0BE2)
            else:self.call('Disable',0x0BE2)

    def close(self):
        super().close();self.atlas=None
