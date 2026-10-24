'use strict';
// Same bounded estimator as flow_beats.py. Only energy observations leave the
// renderer; media URLs, credentials, licenses and decoded samples never do.
function detectBeat(points){
 if(!Array.isArray(points)||points.length<150||points.length>4000)return null;
 const p=[];for(const v of points){if(!Array.isArray(v)||v.length!==3||!v.every(Number.isFinite))return null;
  if(!p.length||v[0]-p.at(-1)[0]>.001)p.push(v);}
 if(p.length<150||p.at(-1)[0]-p[0][0]<3.5)return null;
 const times=[],low=[],mid=[];let j=0;
 for(let n=0;;n++){const t=p[0][0]+n*.01;if(t>=p.at(-1)[0])break;while(j+1<p.length&&p[j+1][0]<t)j++;
  const b=p[Math.min(j+1,p.length-1)],a=p[j],x=b[0]===a[0]?0:(t-a[0])/(b[0]-a[0]);
  times.push(t);low.push(a[1]+(b[1]-a[1])*x);mid.push(a[2]+(b[2]-a[2])*x);}
 const raw=times.map((_,i)=>i?Math.max(0,low[i]-low[i-1])+.35*Math.max(0,mid[i]-mid[i-1]):0);
 const flux=raw.map((v,i)=>.6*v+.2*(raw[i-1]||0)+.2*(raw[i+1]||0));
 const percentile=(values,q)=>{const s=[...values].sort((a,b)=>a-b),n=(s.length-1)*q,k=Math.floor(n);return s[k]+(s[Math.min(k+1,s.length-1)]-s[k])*(n-k);};
 const threshold=Math.max(.006,percentile(flux,.75)*1.4),selected=[];
 for(let i=1;i<flux.length-1;i++)if(flux[i]>threshold&&flux[i]>=flux[i-1]&&flux[i]>flux[i+1]){
  if(selected.length&&times[i]-times[selected.at(-1)]<.16-1e-6){if(flux[i]>flux[selected.at(-1)])selected[selected.length-1]=i;}
  else selected.push(i);}
 if(selected.length<6)return null;
 const beats=selected.map(i=>times[i]),limit=percentile(selected.map(i=>flux[i]),.75)*1.5;
 const weights=selected.map(i=>Math.min(flux[i],limit)),total=weights.reduce((a,b)=>a+b,0);let best=null;
 for(let bpm=80;bpm<=180;bpm+=.25){const period=60/bpm;let real=0,imag=0,r2=0,i2=0,harmonic=1;
  for(let i=0;i<beats.length;i++){const x=beats[i]*2*Math.PI/period;real+=weights[i]*Math.cos(x);imag+=weights[i]*Math.sin(x);r2+=weights[i]*Math.cos(2*x);i2+=weights[i]*Math.sin(2*x);}
  const coverage=Math.min(1,beats.length*period/Math.max(1,beats.at(-1)-beats[0]));
  let coherence=Math.hypot(real,imag)/total;
  if(Math.hypot(r2,i2)/total*.8>coherence){coherence=Math.hypot(r2,i2)/total*.8;real=r2;imag=i2;harmonic=2;}
  const score=coherence*coverage;
  if(!best||score>best.score)best={score,bpm,real,imag,harmonic};}
 const period=60/best.bpm,step=period/best.harmonic,mod=(a,b)=>(a%b+b)%b;
 let phase=mod(Math.atan2(best.imag,best.real),2*Math.PI)*step/(2*Math.PI),aligned=0;const errors=[];
 for(let i=0;i<beats.length;i++){const e=mod(beats[i]-phase+step/2,step)-step/2;
  if(Math.abs(e)<.055){aligned+=weights[i];errors.push(e);}}
 let confidence=Math.min(best.score,aligned/total);
 // Confirm syncopated subdivisions against recurrence of the whole envelope.
 if(confidence<.72&&best.score>=.432&&aligned/total>=.72){
  const mean=flux.reduce((a,b)=>a+b,0)/flux.length,novelty=flux.map(v=>v-mean);
  const lag=period/.01,k=Math.floor(lag),fraction=lag-k;let dot=0,x2=0,y2=0;
  for(let i=0;i<novelty.length-k-1;i++){const x=novelty[i],y=novelty[i+k]*(1-fraction)+novelty[i+k+1]*fraction;dot+=x*y;x2+=x*x;y2+=y*y;}
  const norm=Math.sqrt(x2*y2),recurrence=norm>1e-12?dot/norm:0;
  confidence=Math.min(aligned/total,best.score/.6,recurrence/.25);
 }
 if(confidence<.72)return null;
 phase=mod(phase+percentile(errors,.5),period);
 return {bpm:best.bpm,period,phase,confidence,count:beats.length};
}
function matchBeats(a,b){
 if(!a||!b||Math.min(a.confidence,b.confidence)<.72)return null;
 const options=[.5,1,2].map(factor=>({factor,error:Math.abs(a.bpm/(b.bpm*factor)-1)})).sort((x,y)=>x.error-y.error);
 if(options[0].error>.06)return null;const incomingBpm=b.bpm*options[0].factor;
 return {rate:a.bpm/incomingBpm,bpm:a.bpm,incomingBpm,confidence:Math.min(a.confidence,b.confidence)};
}

// This function runs only inside our authorized MusicKit page. The ordinary
// browser audio graph keeps playback intact; a zero gain silences pre-listen.
function attachTap(a,initialGain=1,readyContext=null){
 const previous=window.__emberFlowAudio;
 if(previous?.media===a){previous.gain.gain.value=initialGain;previous.start();return true;}
 if(previous&&previous.media.paused){previous.stop();previous.context.close().catch(()=>{});}
 const context=readyContext||new AudioContext({latencyHint:'interactive'}),source=context.createMediaElementSource(a),gain=context.createGain();
 gain.gain.value=initialGain;source.connect(gain);gain.connect(context.destination);
 const bass=context.createBiquadFilter();bass.type='lowpass';bass.frequency.value=180;
 const low=context.createAnalyser(),wide=context.createAnalyser();low.fftSize=wide.fftSize=1024;
 source.connect(bass);bass.connect(low);source.connect(wide);
 const data=new Float32Array(1024),points=[];let timer=0,lastTime=-1;
 const energy=node=>{node.getFloatTimeDomainData(data);let sum=0;for(const v of data)sum+=v*v;return Math.log1p(Math.sqrt(sum/data.length)*100);};
 const graph={context,source,gain,media:a,points,
  start(){if(timer)return;source.connect(bass);source.connect(wide);
   timer=setInterval(()=>{if(a.paused||a.ended||context.state!=='running')return;
    const t=context.currentTime-512/context.sampleRate;if(t-lastTime<.004)return;lastTime=t;
    points.push([t,energy(low),energy(wide)]);if(points.length>1600)points.splice(0,points.length-1600);},10);},
  stop(){clearInterval(timer);timer=0;try{source.disconnect(bass);source.disconnect(wide);}catch{};},
  info(){const stamp=context.getOutputTimestamp();return {points:points.slice(-1200),contextTime:context.currentTime,mediaTime:a.currentTime,
    wall:performance.timeOrigin+stamp.performanceTime,outputContext:stamp.contextTime,rate:a.playbackRate,sampleRate:context.sampleRate};}};
 window.__emberFlowAudio=graph;graph.start();context.resume().catch(()=>{});return true;
}
module.exports={detectBeat,matchBeats,attachTap};
