"""Sparse GPU point sprites; no scene screenshots or per-frame SVG rasterisation."""
import ctypes as C
from reveal_gl import RevealGL

VERTEX=b'''#version 150
uniform vec2 viewport;
uniform float dpr;
uniform vec4 flakes[48];
uniform float heights[48];
flat out vec4 snow;
flat out float snowHeight;
void main(){
 snow=flakes[gl_VertexID];snowHeight=heights[gl_VertexID];
 gl_Position=vec4(snow.x/viewport.x*2.-1.,1.-snow.y/viewport.y*2.,0,1);
 gl_PointSize=max(2.,abs(snow.z)*2.*dpr+4.);
}'''

FRAGMENT=b'''#version 150
flat in vec4 snow;
flat in float snowHeight;
uniform vec2 viewport;
uniform float dpr;
uniform float clipRadius;
uniform float topInset;
out vec4 color;
void main(){
 float size=abs(snow.z);
 vec2 q=(gl_PointCoord-.5)*(size*2.+4./dpr);
 bool resting=snow.z<0.;
 float h=max(.35,snowHeight);
 float distance=length(q/vec2(size,h));
 float softness=max(.15,.7/max(1.,size*dpr));
 float alpha=(1.-smoothstep(1.-softness,1.+softness,distance))*snow.w;
 // Soft optical cross on the larger near-plane flakes, no spinning stars.
 if(!resting&&size>1.9){
   float cross=exp(-abs(q.x)*5.)*exp(-abs(q.y)*1.1)+exp(-abs(q.y)*5.)*exp(-abs(q.x)*1.1);
   alpha=max(alpha,cross*snow.w*.09);
 }
 vec2 pixel=vec2(snow.x,snow.y)+q;
 vec2 extent=vec2(viewport.x,viewport.y-2.*topInset);
 vec2 edge=abs(pixel-vec2(viewport.x*.5,viewport.y*.5))-extent*.5+clipRadius;
 float rounded=length(max(edge,vec2(0)))+min(max(edge.x,edge.y),0.)-clipRadius;
 alpha*=1.-smoothstep(-.6,.6,rounded);
 vec3 tint=resting?vec3(.96,.94,.86):vec3(.94,.97,1.);
 color=vec4(tint*alpha,alpha);
}'''


class SnowGL(RevealGL):
    def __init__(self,allow_software=False):
        super().__init__(allow_software,fragment=FRAGMENT,uniforms=('dpr','flakes[0]','heights[0]','clipRadius','topInset'),vertex=VERTEX)
        for name,result,args in (
            ('GetIntegerv',None,(C.c_uint,C.POINTER(C.c_int))),
            ('GetFloatv',None,(C.c_uint,C.POINTER(C.c_float))),
            ('IsEnabled',C.c_ubyte,(C.c_uint,)),('Enable',None,(C.c_uint,)),
            ('ClearColor',None,(C.c_float,)*4),('Clear',None,(C.c_uint,)),
            ('Uniform4fv',None,(C.c_int,C.c_int,C.POINTER(C.c_float))),
            ('Uniform1fv',None,(C.c_int,C.c_int,C.POINTER(C.c_float))),
            ('BlendFuncSeparate',None,(C.c_uint,)*4)):
            call=getattr(self.lib,'gl'+name);call.restype=result;call.argtypes=args;self.functions[name]=call
        self.buffer=(C.c_float*(48*4))();self.heights=(C.c_float*48)()

    def integer(self,name):
        value=C.c_int();self.call('GetIntegerv',name,C.byref(value));return value.value

    def draw(self,width,height,dpr,dots,stage=False):
        count=min(48,len(dots))
        for i,dot in enumerate(dots[:count]):
            for j,value in enumerate(dot[:4]):self.buffer[i*4+j]=value
            self.heights[i]=dot[4] if len(dot)>4 else abs(dot[2])
        program=self.integer(0x8B8D);vao=self.integer(0x85B5)
        viewport=(C.c_int*4)();self.call('GetIntegerv',0x0BA2,viewport)
        clear=(C.c_float*4)();self.call('GetFloatv',0x0C22,clear)
        flags={k:bool(self.call('IsEnabled',k)) for k in (0x0BE2,0x8642,0x0B71,0x0C11)}
        blend=[self.integer(k) for k in (0x80C9,0x80C8,0x80CB,0x80CA)]
        try:
            self.call('Disable',0x0C11);self.call('Disable',0x0B71)
            self.call('Enable',0x8642);self.call('Enable',0x0BE2)
            self.call('BlendFuncSeparate',1,0x0303,1,0x0303)
            self.call('Viewport',0,0,round(width*dpr),round(height*dpr))
            self.call('ClearColor',0.,0.,0.,0.);self.call('Clear',0x00004000)
            self.call('UseProgram',self.program);self.call('BindVertexArray',self.vao)
            self.call('Uniform2f',self.uniforms['viewport'],width,height)
            self.call('Uniform1f',self.uniforms['dpr'],dpr)
            self.call('Uniform1f',self.uniforms['clipRadius'],0. if stage else 22.)
            self.call('Uniform1f',self.uniforms['topInset'],10. if not stage and width<=320 else 0.)
            if count:
                self.call('Uniform4fv',self.uniforms['flakes[0]'],count,self.buffer)
                self.call('Uniform1fv',self.uniforms['heights[0]'],count,self.heights)
            self.call('DrawArrays',0x0000,0,count)
        finally:
            self.call('BindVertexArray',vao);self.call('UseProgram',program)
            self.call('Viewport',*viewport);self.call('ClearColor',*clear)
            self.call('BlendFuncSeparate',*blend)
            for flag,enabled in flags.items():self.call('Enable' if enabled else 'Disable',flag)
