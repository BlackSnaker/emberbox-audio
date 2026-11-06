'use strict';
function validateEQ(value){
 if(value==null)return null;
 if(!value||typeof value!=='object')throw Error('INVALID_ARGUMENTS');
 const copy={};for(const role of ['out','in']){
  const v=value[role];if(!Array.isArray(v)||v.length!==3||!v.every(n=>Number.isFinite(n)&&n>=-12&&n<=0))throw Error('INVALID_ARGUMENTS');
  copy[role]=v.slice();
 }return copy;
}
// Runs inside our authorized page; matches flow_eq.BandEQ exactly.
function installEQ(graph){
 if(graph.eq)return graph.eq;
 const c=graph.context,source=graph.source;
 const alphas=[180,5000].map(f=>1-Math.exp(-2*Math.PI*f/c.sampleRate));
 const low=c.createIIRFilter([alphas[0]],[1,alphas[0]-1]),high=c.createIIRFilter([alphas[1]],[1,alphas[1]-1]);
 const direct=c.createGain(),lowGain=c.createGain(),highGain=c.createGain();
 lowGain.gain.value=highGain.gain.value=0;direct.gain.value=1;
 source.disconnect(graph.gain);source.connect(direct);source.connect(low);source.connect(high);
 direct.connect(graph.gain);low.connect(lowGain);high.connect(highGain);lowGain.connect(graph.gain);highGain.connect(graph.gain);
 const nodes=[direct,lowGain,highGain];
 graph.eq={
  schedule(db,incoming,start,duration){
   const g=db.map(v=>10**(v/20)),n=Math.ceil(c.sampleRate*.03);let norm=0;
   for(let i=0;i<n;i++)norm+=Math.abs((i===0?g[2]:0)+(g[0]-g[1])*alphas[0]*(1-alphas[0])**i+(g[1]-g[2])*alphas[1]*(1-alphas[1])**i);
   norm=Math.max(1,norm+Math.abs(g[0]-g[1])*(1-alphas[0])**n+Math.abs(g[1]-g[2])*(1-alphas[1])**n);
   const values=nodes.map(()=>new Float32Array(257));
   for(let i=0;i<257;i++){
    const t=i/256,s=t*t*t*(t*(t*6-15)+10),w=incoming?1-s:s;
    values[0][i]=1-w+w*g[2]/norm;values[1][i]=w*(g[0]-g[1])/norm;values[2][i]=w*(g[1]-g[2])/norm;
   }
   nodes.forEach((node,i)=>{node.gain.cancelScheduledValues(0);node.gain.setValueCurveAtTime(values[i],start,duration);});
   return norm;
  },
  release(){
   nodes.forEach((node,i)=>{const p=node.gain;
    p.cancelAndHoldAtTime(c.currentTime);p.linearRampToValueAtTime(i===0?1:0,c.currentTime+.08);
   });
  }
 };return graph.eq;
}
module.exports={validateEQ,installEQ};
