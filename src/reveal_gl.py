"""Small OpenGL renderer for the entrance; uses the system GL dispatch library.

No PyOpenGL dependency. GTK owns the context and framebuffer. All calls happen
on GTK's thread with that context current; failure selects the plain fade.
"""
import ctypes as C
from ctypes.util import find_library


VERTEX=b'''#version 150
out vec2 uv;
void main(){
  vec2 p=vec2((gl_VertexID==1)?3.0:-1.0,(gl_VertexID==2)?3.0:-1.0);
  uv=vec2((p.x+1.0)*.5,1.0-(p.y+1.0)*.5);
  gl_Position=vec4(p,0,1);
}'''
FRAGMENT=b'''#version 150
in vec2 uv;
out vec4 color;
uniform vec2 viewport;
uniform vec4 shell;
uniform vec4 artwork;
uniform vec3 pigment;
uniform float progress;
uniform int hasCover;
uniform sampler2D cover;
uniform sampler2D room;
uniform int hasRoom;
uniform sampler2D previous;
uniform int hasPrevious;
float ease(float t){t=clamp(t,0.0,1.0);return t*t*(3.0-2.0*t);}
vec4 over(vec4 a,vec4 b){return a+b*(1.0-a.a);}
float rounded(vec2 p,vec4 box,float radius){
  vec2 q=abs(p-box.xy-box.zw*.5)-box.zw*.5+radius;
  float d=length(max(q,vec2(0)))+min(max(q.x,q.y),0.0)-radius;
  return 1.0-smoothstep(-.7,.7,d);
}
void main(){
  vec2 p=uv*viewport;
  float atmosphere=ease((progress-.04)/.56);
  vec2 a=(uv-vec2(.21,.35))/vec2(.59,.78);
  vec2 b=(uv-vec2(.92,.09))/vec2(.43,.72);
  vec3 bg=vec3(.106,.129,.106);
  bg=mix(bg,pigment,.58*max(0.0,1.0-length(a)));
  bg=mix(bg,vec3(.62,.45,.22),.16*max(0.0,1.0-length(b)));
  bg=mix(bg,vec3(.047,.071,.055),.65*uv.y);
  if(hasPrevious==1){
    vec4 old=texture(previous,uv);
    vec4 next=texture(room,uv);
    float blend=ease((progress-.12*uv.y)/.88);
    vec4 base=over(mix(old,next,blend),vec4(bg,1));
    vec4 frame=vec4(artwork.xy-9.0,artwork.zw+18.0);
    float rim=.6*rounded(p,frame,30.0);
    base=over(vec4(vec3(.067,.082,.067)*rim,rim),base);
    vec2 at=(p-artwork.xy)/max(vec2(1),artwork.zw);
    if(hasCover==1 && all(greaterThanEqual(at,vec2(0))) && all(lessThanEqual(at,vec2(1)))){
      vec4 tex=texture(cover,at);tex.a*=rounded(p,artwork,clamp(artwork.z*.04,6.0,22.0));
      base=over(vec4(tex.rgb*tex.a,tex.a),base);
    }
    color=base;return;
  }
  vec4 scene=vec4(bg*atmosphere,atmosphere);
  float mask=rounded(p,shell,min(26.0,min(shell.z,shell.w)*.15));
  float opacity=mask*(1.0-ease((progress-.35)/.5));
  scene=over(vec4(vec3(.173,.173,.161)*opacity,opacity),scene);
  vec2 at=(p-artwork.xy)/max(vec2(1),artwork.zw);
  if(hasCover==1 && all(greaterThanEqual(at,vec2(0))) && all(lessThanEqual(at,vec2(1)))){
    vec4 tex=texture(cover,at);
    tex.a*=rounded(p,artwork,clamp(artwork.z*.04,6.0,22.0));
    scene=over(vec4(tex.rgb*tex.a,tex.a),scene);
  }
  if(hasRoom==1){
    vec4 destination=over(texture(room,uv),vec4(bg,1.0));
    color=mix(scene,destination,ease((progress-.58)/.42));
  }else color=scene*(1.0-ease((progress-.76)/.24));
}'''


class RevealGL:
    def __init__(self,allow_software=False):
        name=find_library('GL')
        if not name:raise RuntimeError('System OpenGL unavailable')
        self.lib=C.CDLL(name)
        renderer=self.lib.glGetString
        renderer.restype=C.c_char_p;renderer.argtypes=[C.c_uint]
        self.renderer=(renderer(0x1F01) or b'').decode(errors='replace')
        if not allow_software and any(name in self.renderer.lower() for name in ('llvmpipe','softpipe','swrast','software rasterizer')):
            raise RuntimeError('Software OpenGL: use compositor fade')
        self.program=self.vao=self.texture=self.room_texture=self.previous_texture=0
        self.uploaded=self.room_uploaded=self.previous_uploaded=None
        u,i,f,p=C.c_uint,C.c_int,C.c_float,C.c_void_p
        self.functions={}
        signatures={
            'CreateShader':(u,u),'ShaderSource':(None,u,i,C.POINTER(C.c_char_p),p),
            'CompileShader':(None,u),'GetShaderiv':(None,u,u,C.POINTER(i)),
            'DeleteShader':(None,u),'CreateProgram':(u,),
            'AttachShader':(None,u,u),'LinkProgram':(None,u),
            'GetProgramiv':(None,u,u,C.POINTER(i)),'DeleteProgram':(None,u),
            'UseProgram':(None,u),'GenVertexArrays':(None,i,C.POINTER(u)),
            'BindVertexArray':(None,u),'DeleteVertexArrays':(None,i,C.POINTER(u)),
            'GenTextures':(None,i,C.POINTER(u)),'BindTexture':(None,u,u),
            'DeleteTextures':(None,i,C.POINTER(u)),'ActiveTexture':(None,u),
            'TexParameteri':(None,u,u,i),'PixelStorei':(None,u,i),
            'TexImage2D':(None,u,i,i,i,i,i,u,u,p),
            'GetUniformLocation':(i,u,C.c_char_p),'Uniform1f':(None,i,f),
            'Uniform1i':(None,i,i),'Uniform2f':(None,i,f,f),
            'Uniform3f':(None,i,f,f,f),'Uniform4f':(None,i,f,f,f,f),
            'DrawArrays':(None,u,i,i),'Disable':(None,u),'Finish':(None,),
            'Viewport':(None,i,i,i,i),
        }
        for name,(result,*args) in signatures.items():
            call=getattr(self.lib,'gl'+name);call.restype=result;call.argtypes=args
            self.functions[name]=call
        shaders=[]
        try:
            for kind,source in ((0x8B31,VERTEX),(0x8B30,FRAGMENT)):
                shader=self.call('CreateShader',kind);shaders.append(shader)
                text=C.c_char_p(source)
                self.call('ShaderSource',shader,1,C.byref(text),None)
                self.call('CompileShader',shader)
                status=i();self.call('GetShaderiv',shader,0x8B81,C.byref(status))
                if not status.value:raise RuntimeError('Entrance shader compilation failed')
            self.program=self.call('CreateProgram')
            for shader in shaders:self.call('AttachShader',self.program,shader)
            self.call('LinkProgram',self.program)
            status=i();self.call('GetProgramiv',self.program,0x8B82,C.byref(status))
            if not status.value:raise RuntimeError('Entrance shader linking failed')
            value=u();self.call('GenVertexArrays',1,C.byref(value));self.vao=value.value
            self.call('GenTextures',1,C.byref(value));self.texture=value.value
            self.call('GenTextures',1,C.byref(value));self.room_texture=value.value
            self.call('GenTextures',1,C.byref(value));self.previous_texture=value.value
            self.uniforms={name:self.call('GetUniformLocation',self.program,name.encode()) for name in
                           ('viewport','shell','artwork','pigment','progress','hasCover','cover','room','hasRoom','previous','hasPrevious')}
        except Exception:
            self.close();raise
        finally:
            for shader in shaders:self.call('DeleteShader',shader)

    def call(self,name,*args):
        return self.functions[name](*args)

    def upload(self,pixels):
        if pixels is self.uploaded:return
        self.uploaded=pixels
        if pixels is None:return
        w,h,channels=pixels.get_width(),pixels.get_height(),pixels.get_n_channels()
        stride=pixels.get_rowstride();raw=pixels.get_pixels()
        data=b''.join(raw[y*stride:y*stride+w*channels] for y in range(h))
        buffer=C.create_string_buffer(data)
        self.call('BindTexture',0x0DE1,self.texture)
        self.call('PixelStorei',0x0CF5,1)
        self.call('PixelStorei',0x0CF2,0)
        for name,value in ((0x2801,0x2601),(0x2800,0x2601),(0x2802,0x812F),(0x2803,0x812F)):
            self.call('TexParameteri',0x0DE1,name,value)
        self.call('TexImage2D',0x0DE1,0,0x8058,w,h,0,0x1908 if channels==4 else 0x1907,0x1401,buffer)

    def raw_texture(self,texture,frame):
        w,h,data=frame
        self.call('BindTexture',0x0DE1,texture)
        for name,value in ((0x2801,0x2601),(0x2800,0x2601),(0x2802,0x812F),(0x2803,0x812F)):
            self.call('TexParameteri',0x0DE1,name,value)
        self.call('PixelStorei',0x0CF5,1);self.call('PixelStorei',0x0CF2,0)
        self.call('TexImage2D',0x0DE1,0,0x8058,w,h,0,0x80E1,0x1401,C.create_string_buffer(data))

    def draw(self,width,height,shell,artwork,pigment,progress,pixels,room=None,previous=None):
        self.call('Disable',0x0BE2)  # The shader outputs premultiplied alpha.
        self.call('UseProgram',self.program);self.call('BindVertexArray',self.vao)
        self.call('ActiveTexture',0x84C0);self.upload(pixels)
        self.call('BindTexture',0x0DE1,self.texture)
        self.call('ActiveTexture',0x84C1)
        self.call('BindTexture',0x0DE1,self.room_texture)
        if room is not None and room is not self.room_uploaded:
            self.room_uploaded=room
            self.raw_texture(self.room_texture,room)
        self.call('ActiveTexture',0x84C2);self.call('BindTexture',0x0DE1,self.previous_texture)
        if previous is not None and previous is not self.previous_uploaded:
            self.previous_uploaded=previous;self.raw_texture(self.previous_texture,previous)
        for name,kind,values in (
                ('viewport','2f',(width,height)),('shell','4f',shell),('artwork','4f',artwork),
                ('pigment','3f',pigment),('progress','1f',(progress,)),
                ('hasCover','1i',(int(pixels is not None),)),('cover','1i',(0,)),
                ('hasRoom','1i',(int(room is not None),)),('room','1i',(1,))):
            self.call('Uniform'+kind,self.uniforms[name],*values)
        for name,kind,values in (
                ('previous','1i',(2,)),('hasPrevious','1i',(int(previous is not None),))):
            self.call('Uniform'+kind,self.uniforms[name],*values)
        self.call('DrawArrays',0x0004,0,3)
        self.call('BindVertexArray',0);self.call('UseProgram',0)
        self.call('BindTexture',0x0DE1,0)
        self.call('ActiveTexture',0x84C0);self.call('BindTexture',0x0DE1,0)

    def close(self):
        if self.texture:self.call('DeleteTextures',1,C.byref(C.c_uint(self.texture)))
        if self.room_texture:self.call('DeleteTextures',1,C.byref(C.c_uint(self.room_texture)))
        if self.previous_texture:self.call('DeleteTextures',1,C.byref(C.c_uint(self.previous_texture)))
        if self.vao:self.call('DeleteVertexArrays',1,C.byref(C.c_uint(self.vao)))
        if self.program:self.call('DeleteProgram',self.program)
        self.program=self.vao=self.texture=self.room_texture=self.previous_texture=0
        self.uploaded=self.room_uploaded=self.previous_uploaded=None
