"""A local, texture-cached water ripple for album artwork.

GTK owns the GL context and the transition clock. Only the two immutable cover
snapshots cross the CPU/GPU boundary; waiting and reveal frames run in GLSL.
"""
import ctypes as C
import math

from reveal_gl import RevealGL


FRAGMENT=b'''#version 150
in vec2 uv;
out vec4 color;
uniform vec2 viewport;
uniform sampler2D cover;
uniform sampler2D room;
uniform int hasCover;
uniform int hasRoom;
uniform float elapsed;
uniform float reveal;
uniform float cornerRadius;

float ease(float t){t=clamp(t,0.0,1.0);return t*t*t*(t*(t*6.0-15.0)+10.0);}
float edgeDistance(vec2 p){
  float radius=min(cornerRadius,min(viewport.x,viewport.y)*.5);
  vec2 q=abs(p-viewport*.5)-viewport*.5+radius;
  return length(max(q,vec2(0)))+min(max(q.x,q.y),0.0)-radius;
}
vec4 premultiply(vec4 c){return vec4(c.rgb*c.a,c.a);}
vec2 safeUV(vec2 p){
  vec2 halfPixel=.5/max(viewport,vec2(1));
  return clamp(p,halfPixel,vec2(1)-halfPixel);
}

void main(){
  float mask=1.0-smoothstep(-.7,.7,edgeDistance(uv*viewport));
  if(hasCover==0 && hasRoom==0){color=vec4(0);return;}
  // The settled frame is exactly the original new image, with no colour grade,
  // ripple, light, zoom or residual old texture. This also avoids a final pop.
  if(reveal>=.999999 && hasRoom==1){
    color=premultiply(texture(room,uv))*mask;return;
  }

  float scale=min(viewport.x,viewport.y);
  vec2 centre=vec2(.435,.415);
  vec2 radial=(uv-centre)*viewport/max(1.0,scale);
  float distance=length(radial);
  vec2 direction=radial/max(.0001,distance);
  float t=mod(max(0.0,elapsed),2.9);
  float strength=(elapsed<2.9?1.0:.30)*ease(t/.13);
  strength*=exp(-.40*t)*(1.0-ease((t-1.65)/.85));
  strength*=1.0-ease((reveal-.48)/.52);

  // Three dispersing circular crests. Each is finite and leaves the image;
  // a much softer impact repeats only if playback preparation takes longer.
  float slope=0.0;
  float width=.018+.006*t;
  for(int i=0;i<3;i++){
    float x=(distance-(.025+.57*t-float(i)*.058))/width;
    slope+=-x*exp(-.5*x*x)*(1.0-float(i)*.21);
  }
  slope*=strength;

  // Readiness reveals the next cover through a broad liquid front, independent
  // of how long it took to arrive. Its optical ridge joins the waiting ripple.
  vec2 farthest=max(centre,vec2(1)-centre)*viewport/max(1.0,scale);
  float front=mix(-.20,length(farthest)+.20,reveal);
  float blend=hasRoom==1?1.0-ease((distance-front+.125)/.25):0.0;
  float ridge=(distance-front)/.033;
  float moving=sin(clamp(reveal,0.0,1.0)*3.14159265);
  slope+=-.62*ridge*exp(-.5*ridge*ridge)*moving;

  vec2 offset=direction*slope*.0056*scale/max(viewport,vec2(1));
  vec4 oldImage=hasCover==1?premultiply(texture(cover,safeUV(uv+offset))):
                                premultiply(texture(room,safeUV(uv+offset)));
  vec4 newImage=hasRoom==1?premultiply(texture(room,safeUV(uv+offset*.68))):oldImage;
  vec4 image=mix(oldImage,newImage,blend);

  // A restrained grazing reflection catches each crest instead of drawing
  // opaque rings on the photograph. All shading fades fully with readiness.
  float light=dot(direction,normalize(vec2(-.65,-.76)))*slope;
  float sheen=max(0.0,light)*.050;
  float shade=max(0.0,-light)*.024;
  image.rgb=image.rgb*(1.0-shade)+vec3(1.0,.84,.57)*sheen*image.a;
  float rim=exp(-pow((edgeDistance(uv*viewport)+1.15)/1.25,2.0));
  float rimLight=rim*.018*(strength+moving*.25);
  image.rgb+=vec3(1.0,.86,.64)*rimLight*image.a;
  color=vec4(clamp(image.rgb,vec3(0),vec3(image.a)),image.a)*mask;
}'''


class CoverRippleGL(RevealGL):
    """Draw the old/new artwork only; no window snapshots or frame allocation."""

    def __init__(self,allow_software=False):
        super().__init__(allow_software,fragment=FRAGMENT,uniforms=('elapsed','reveal'))
        self.room_size=None
        for name,result,args in (
                ('GetIntegerv',None,(C.c_uint,C.POINTER(C.c_int))),
                ('IsEnabled',C.c_ubyte,(C.c_uint,)),
                ('Enable',None,(C.c_uint,)),
                ('BindBuffer',None,(C.c_uint,C.c_uint))):
            call=getattr(self.lib,'gl'+name)
            call.restype=result;call.argtypes=args;self.functions[name]=call

    def _integer(self,name):
        value=C.c_int();self.call('GetIntegerv',name,C.byref(value))
        return value.value

    def _upload_next(self,pixels):
        if pixels is self.room_uploaded:return
        if pixels is None:
            self.room_uploaded=None;return
        w,h,channels=pixels.get_width(),pixels.get_height(),pixels.get_n_channels()
        stride=pixels.get_rowstride();raw=pixels.get_pixels()
        data=raw if stride==w*channels else b''.join(raw[y*stride:y*stride+w*channels] for y in range(h))
        self.call('BindTexture',0x0DE1,self.room_texture)
        self.call('PixelStorei',0x0CF5,1);self.call('PixelStorei',0x0CF2,0)
        for name,value in ((0x2801,0x2601),(0x2800,0x2601),(0x2802,0x812F),(0x2803,0x812F)):
            self.call('TexParameteri',0x0DE1,name,value)
        kind=0x1908 if channels==4 else 0x1907
        buffer=C.c_char_p(data)
        if self.room_size==(w,h,channels):
            self.call('TexSubImage2D',0x0DE1,0,0,0,w,h,kind,0x1401,buffer)
        else:
            self.call('TexImage2D',0x0DE1,0,0x8058,w,h,0,kind,0x1401,buffer)
            self.room_size=(w,h,channels)
        self.room_uploaded=pixels

    def draw(self,width,height,old,new,age,reveal,radius=22):
        width=max(1,int(width));height=max(1,int(height))
        age=max(0.0,float(age)) if math.isfinite(float(age)) else 0.0
        reveal=min(1.0,max(0.0,float(reveal))) if math.isfinite(float(reveal)) else 0.0
        radius=max(0.0,float(radius)) if math.isfinite(float(radius)) else 22.0
        # Save every context state this renderer touches. GTK may reuse its
        # context for another GLArea, including the fullscreen entrance.
        program=self._integer(0x8B8D);vao=self._integer(0x85B5)
        active=self._integer(0x84E0);blend=bool(self.call('IsEnabled',0x0BE2))
        viewport=(C.c_int*4)();self.call('GetIntegerv',0x0BA2,viewport)
        unpack={key:self._integer(key) for key in (0x0CF5,0x0CF2,0x0CF3,0x0CF4)}
        unpack_buffer=self._integer(0x88EF)
        bindings=[]
        for unit in (0x84C0,0x84C1):
            self.call('ActiveTexture',unit);bindings.append(self._integer(0x8069))
        try:
            self.call('Disable',0x0BE2)
            self.call('Viewport',0,0,width,height)
            self.call('UseProgram',self.program);self.call('BindVertexArray',self.vao)
            self.call('BindBuffer',0x88EC,0)
            self.call('PixelStorei',0x0CF3,0);self.call('PixelStorei',0x0CF4,0)
            self.call('ActiveTexture',0x84C0);self.upload(old)
            self.call('BindTexture',0x0DE1,self.texture)
            self.call('ActiveTexture',0x84C1);self._upload_next(new)
            self.call('BindTexture',0x0DE1,self.room_texture)
            for name,kind,values in (
                    ('viewport','2f',(width,height)),('elapsed','1f',(age,)),
                    ('reveal','1f',(reveal if new is not None else 0.0,)),
                    ('cornerRadius','1f',(radius,)),('cover','1i',(0,)),('room','1i',(1,)),
                    ('hasCover','1i',(int(old is not None),)),('hasRoom','1i',(int(new is not None),))):
                self.call('Uniform'+kind,self.uniforms[name],*values)
            self.call('DrawArrays',0x0004,0,3)
        finally:
            self.call('BindVertexArray',vao);self.call('UseProgram',program)
            for unit,binding in zip((0x84C0,0x84C1),bindings):
                self.call('ActiveTexture',unit);self.call('BindTexture',0x0DE1,binding)
            self.call('ActiveTexture',active)
            for key,value in unpack.items():self.call('PixelStorei',key,value)
            self.call('BindBuffer',0x88EC,unpack_buffer)
            self.call('Viewport',*viewport)
            if blend:self.call('Enable',0x0BE2)
            else:self.call('Disable',0x0BE2)

    def forget(self):
        """Drop snapshots without requiring a current GL context.

        Two allocated cover textures remain bounded and reusable. Clearing
        identity caches makes a later transition upload its current snapshots.
        """
        self.uploaded=self.room_uploaded=self.previous_uploaded=None

    def close(self):
        super().close();self.room_size=None
