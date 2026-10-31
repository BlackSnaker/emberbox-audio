"""Cover-only pause refraction, isolated from the track-change shader."""
from cover_ripple_gl import CoverRippleGL

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

vec4 restingCover(){
  float depth=reveal;
  if(depth<=.000001 && (elapsed<=.000001 || elapsed>=1.7)){
    return premultiply(texture(cover,uv))*(1.0-smoothstep(-.7,.7,edgeDistance(uv*viewport)));
  }
  float scale=min(viewport.x,viewport.y);
  // A fixed socket stays in the body while the print settles into it. Its
  // top shadow and lower grazing light describe depth without greying the art.
  vec2 inset=vec2(.021)*depth;
  vec2 origin=inset+vec2(0,.003)*depth;
  vec2 span=vec2(1)-2.0*inset;
  vec2 at=(uv-origin)/span;
  vec2 q=abs((uv-origin-span*.5)*viewport)-span*viewport*.5+cornerRadius;
  float edge=length(max(q,vec2(0)))+min(max(q.x,q.y),0.0)-cornerRadius;
  float coverMask=1.0-smoothstep(-.7,.7,edge);
  vec2 radial=(at-vec2(.46,.44))*viewport/max(1.0,scale);
  float d=length(radial);
  vec2 direction=radial/max(.0001,d);
  float t=max(0.0,elapsed);
  float envelope=ease(t/.11)*(1.0-ease((t-1.05)/.65))*exp(-.65*t);
  float slope=0.0;
  for(int i=0;i<3;i++){
    float x=(d-(.015+.56*t-float(i)*.066))/(.023+.011*t);
    slope+=-x*exp(-.5*x*x)*(1.0-float(i)*.23);
  }
  slope*=envelope;
  vec2 offset=direction*slope*.0048*scale/max(viewport,vec2(1));
  vec4 image=premultiply(texture(cover,safeUV(at+offset)))*coverMask;
  float light=dot(direction,normalize(vec2(-.65,-.76)))*slope;
  image.rgb=image.rgb*(1.0-max(0.0,-light)*.035)+vec3(1,.87,.63)*max(0.0,light)*.075*image.a;
  float topShadow=exp(-max(0.0,at.y)*scale/max(2.0,cornerRadius*.55))*.23*depth;
  float sideShadow=exp(-max(0.0,at.x)*scale/max(2.0,cornerRadius*.41))*.10*depth;
  image.rgb*=1.0-topShadow-sideShadow;
  float bottomRim=exp(-pow((edge+cornerRadius*.06)/max(.7,cornerRadius*.05),2.0))*max(0.0,at.y-.45)*.06*depth;
  image.rgb+=vec3(.90,.83,.64)*bottomRim*image.a;
  float socketShade=exp(-uv.y*scale/10.0)*.32;
  vec3 socket=vec3(.076,.091,.075)*(1.0-socketShade);
  vec4 well=vec4(socket*depth,depth);
  vec4 result=image+well*(1.0-image.a);
  float mask=1.0-smoothstep(-.7,.7,edgeDistance(uv*viewport));
  return vec4(clamp(result.rgb,vec3(0),vec3(result.a)),result.a)*mask;
}

void main(){color=hasCover==1?restingCover():vec4(0);}
'''


class CoverPauseGL(CoverRippleGL):
    def __init__(self,allow_software=False):
        super().__init__(allow_software,fragment=FRAGMENT)
        self.reveal_without_new=True
