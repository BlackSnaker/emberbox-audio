'use strict';
const {detectBeat,matchBeats,attachTap}=require('./rhythm.cjs');
// Three C2-continuous phases: reveal the intro, exchange the foreground,
// release the old ambience. The complementary gains retain peak headroom.
// The same curve drives mpv (flow_youtube.py); tests compare both engines.
function mixCurve(position){
 const t=Math.max(0,Math.min(1,position));let x,start,span;
 if(t<.38){x=t/.38;start=0;span=.18;}
 else if(t<.62){x=(t-.38)/.24;start=.18;span=.64;}
 else{x=(t-.62)/.38;start=.82;span=.18;}
 return start+span*x*x*x*(x*(x*6-15)+10);
}
// MusicKit keeps its media elements detached from the DOM. Resolve the ordinary
// already-authorized element, without reading media URLs, credentials or keys.
const MEDIA=`(()=>{if(window.__emberFlowMedia)return window.__emberFlowMedia;
 const root=window.MusicKit?.getInstance?.();if(!root)return null;
 const queue=[[root,0]],seen=new Set();let count=0;
 while(queue.length&&count++<1600){const [v,d]=queue.shift();
  if(!v||typeof v!=='object'||seen.has(v))continue;seen.add(v);
  if(v._targetElement instanceof HTMLMediaElement){window.__emberFlowPlayer=v;return window.__emberFlowMedia=v._targetElement;}
  if(v instanceof HTMLMediaElement)return window.__emberFlowMedia=v;
  if(d>8||v===window||v instanceof Node)continue;
  if(v instanceof Map){for(const x of v.values())queue.push([x,d+1]);continue;}
  let props;try{props=Object.getOwnPropertyDescriptors(v);}catch{continue;}
  for(const [key,p] of Object.entries(props))if(!/api|token|auth|user|library|lyrics|prototype/i.test(key)&&p.value&&typeof p.value==='object')queue.push([p.value,d+1]);
 }return null;})()`;
const RELEASE=`(()=>{window.__emberFlowRelease?.();clearInterval(window.__emberFlowTimer);
 clearInterval(window.__emberFlowRateTimer);
 const graph=window.__emberFlowAudio;if(graph){graph.stop();graph.gain.gain.cancelScheduledValues(0);graph.gain.gain.value=1;}
 const a=window.__emberFlowMedia,base=window.__emberFlowVolume;
 if(a){a.playbackRate=1;a.preservesPitch=true;}
 if(a&&Number.isFinite(base)){delete a.volume;Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype,'volume').set.call(a,base);}
 if(a&&window.__emberFlowVolumeGuard)a.removeEventListener('volumechange',window.__emberFlowVolumeGuard,true);
 delete window.__emberFlowVolumeGuard;delete window.__emberFlowVolume;delete window.__emberFlowMultiplier;
 delete window.__emberFlowMedia;delete window.__emberFlowPlayer;})()`;

class FlowDecks {
 constructor(current,make,request,url){Object.assign(this,{current,make,request,url,next:null,old:null,timer:null,key:'',generation:0,pendingState:null,beatSync:false});}
 async inspect(win){
  const s=await win.webContents.executeJavaScript(`(()=>{const a=${MEDIA};return a?{playing:!a.paused&&!a.ended,ended:a.ended,error:!!a.error,time:a.currentTime,rate:a.playbackRate,volume:Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype,'volume').get.call(a)*(window.__emberFlowAudio?.media===a?window.__emberFlowAudio.gain.gain.value:1)}:null;})()`);
  return s?{...s,audible:win.webContents.isCurrentlyAudible()}:null;
 }
 async rhythm(win){return win.webContents.executeJavaScript('window.__emberFlowAudio?.info()||null');}
 async tap(win,gain=1){return win.webContents.executeJavaScript(`(async()=>{const a=${MEDIA};if(!a)return false;
  if(window.__emberFlowAudio?.media===a)return (${attachTap.toString()})(a,${gain});
  const context=new AudioContext({latencyHint:'interactive'});let timer;
  try{await Promise.race([context.resume(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('FLOW_NOT_READY')),750);})]);
   return (${attachTap.toString()})(a,${gain},context);
  }catch(e){context.close().catch(()=>{});throw e;}finally{clearTimeout(timer);}})()`);}
 async gain(win,to,duration=0,from=to,startsAt=Date.now()){return win.webContents.executeJavaScript(`(()=>{const a=${MEDIA};if(!a)throw Error('FLOW_UNAVAILABLE');
  const nativeVolume=Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype,'volume');
  if(window.__emberFlowVolume===undefined){window.__emberFlowVolume=a.volume;
    Object.defineProperty(a,'volume',{configurable:true,get(){return window.__emberFlowVolume;},set(v){window.__emberFlowVolume=v;nativeVolume.set.call(a,v*(window.__emberFlowAudio?.media===a?1:window.__emberFlowMultiplier??1));}});}
  if(!window.__emberFlowVolumeGuard){window.__emberFlowVolumeGuard=e=>e.stopImmediatePropagation();a.addEventListener('volumechange',window.__emberFlowVolumeGuard,true);}
  clearInterval(window.__emberFlowTimer);
  const graph=window.__emberFlowAudio;
  if(graph?.media===a){
   nativeVolume.set.call(a,window.__emberFlowVolume);
   const stamp=graph.context.getOutputTimestamp(),wall=performance.timeOrigin+stamp.performanceTime;
   const start=Math.max(graph.context.currentTime,stamp.contextTime+(${Number(startsAt)}-wall)/1000);
   const values=new Float32Array(1025),curve=${mixCurve.toString()};
   for(let i=0;i<values.length;i++)values[i]=${from}+(${to}-${from})*curve(i/(values.length-1));
   graph.gain.gain.cancelScheduledValues(0);
   if(${duration}>0)graph.gain.gain.setValueCurveAtTime(values,start,${duration});else graph.gain.gain.value=${to};
   return true;
  }
  const start=performance.now()+(${Number(startsAt)}-Date.now()),set=Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype,'volume').set;
  const envelope=${mixCurve.toString()};
  const step=()=>{const t=${duration}>0?Math.max(0,Math.min(1,(performance.now()-start)/(${duration}*1000))):1;
   const x=envelope(t);window.__emberFlowMultiplier=${from}+(${to}-${from})*x;
   set.call(a,window.__emberFlowVolume*window.__emberFlowMultiplier);if(t>=1)clearInterval(window.__emberFlowTimer);};
  step();if(${duration}>0)window.__emberFlowTimer=setInterval(step,16);return true;})()`);}
 async cancel(){
  this.generation++;clearTimeout(this.timer);this.timer=null;this.pendingState=null;this.key='';
  for(const w of [this.next,this.old])if(w&&!w.isDestroyed())w.destroy();
  this.next=this.old=null;
  if(!this.current.isDestroyed())await this.current.webContents.executeJavaScript(RELEASE).catch(()=>{});
 }
 async prepare(p){
  if(!['songs','library-songs'].includes(p.kind)||!/^\w[\w.-]{0,199}$/.test(String(p.id))||
    typeof p.key!=='string'||p.key.length>80)throw Error('INVALID_ARGUMENTS');
  if(this.key===p.key&&this.next)return {ready:true};
  await this.cancel();this.beatSync=p.beatSync===true;const generation=this.generation,w=this.make(false);this.next=w;
  if(this.beatSync)await this.tap(this.current).catch(()=>false);
  w.webContents.setBackgroundThrottling?.(true);
  const alive=()=>generation===this.generation&&!w.isDestroyed();
  try{
   const until=Date.now()+11000;
   await Promise.race([w.loadURL(this.url),new Promise((_,reject)=>setTimeout(()=>reject(Error('FLOW_NOT_READY')),8000))]);
   while(Date.now()<until){if(!alive())throw Error('FLOW_CANCELLED');
    const s=await this.request(w,{method:'status'});if(s.authorized&&s.ready)break;
    await new Promise(r=>setTimeout(r,150));}
   if(!alive())throw Error('FLOW_CANCELLED');
   await this.request(w,{method:'play',params:{kind:p.kind,id:p.id,paused:true}});
   if(!alive())throw Error('FLOW_CANCELLED');this.key=p.key;return {ready:true};
  }catch(e){if(this.next===w){this.next=null;this.key='';}if(!w.isDestroyed())w.destroy();throw e;}
 }
 async holdTail(win){
  return win.webContents.executeJavaScript(`(()=>{const a=${MEDIA},p=window.__emberFlowPlayer,m=MusicKit.getInstance();
   if(!a||a.paused||a.ended)throw Error('FLOW_NOT_READY');
   const undo=[];let released=false;
   for(const [object,key] of [[p,'pause'],[p,'stop'],[a,'pause']]){
    if(!object||typeof object[key]!=='function')continue;
    const own=Object.getOwnPropertyDescriptor(object,key);
    object[key]=()=>Promise.resolve();undo.push(()=>{if(own)Object.defineProperty(object,key,own);else delete object[key];});}
   const release=()=>{if(released)return;released=true;for(const f of undo)f();m.removeEventListener?.('mediaPlaybackError',release);};
   window.__emberFlowRelease=release;m.addEventListener?.('mediaPlaybackError',release);
   // A bounded lease survives a lost IPC connection. EME/CDM checks remain intact.
   setTimeout(()=>{if(!released){release();a.pause();}},24000);return true;})()`);
 }
 async startMuted(win,beats=false){
  await win.webContents.executeJavaScript(`(()=>{const proto=HTMLMediaElement.prototype,play=proto.play,
   volume=Object.getOwnPropertyDescriptor(proto,'volume');
   const release=()=>{if(proto.play===hook)proto.play=play;};
   const hook=function(){release();const a=this;window.__emberFlowMedia=a;window.__emberFlowVolume=a.volume;
    window.__emberFlowMultiplier=0;
    Object.defineProperty(a,'volume',{configurable:true,get(){return window.__emberFlowVolume;},set(v){
      window.__emberFlowVolume=v;volume.set.call(a,v*(window.__emberFlowAudio?.media===a?1:window.__emberFlowMultiplier??1));}});
    window.__emberFlowVolumeGuard=e=>e.stopImmediatePropagation();a.addEventListener('volumechange',window.__emberFlowVolumeGuard,true);
    let graph=false;if(${beats===true}){try{graph=(${attachTap.toString()})(a,0);}catch{}}
    volume.set.call(a,graph?window.__emberFlowVolume:0);return play.call(a);};
   proto.play=hook;window.__emberFlowRelease=release;setTimeout(release,4000);return true;})()`);
 }
 async align(next,oldInfo,incoming,generation,notBefore=Date.now()+180){
  const a=detectBeat(oldInfo?.points),b=detectBeat(incoming?.points),plan=matchBeats(a,b);
  // Rewind the unheard preview in every case. A low-confidence song must keep
  // its opening and its ordinary speed, even when matching is unavailable.
  const bounded=async(request)=>{let timer;try{return await Promise.race([this.request(next,request),
   new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('FLOW_NOT_READY')),1800);})]);}finally{clearTimeout(timer);}};
  await bounded({method:'transport',params:{action:'pause'}});
  // MusicKit's seek promise can stall on a paused deck. Rewind its ordinary
  // media element and wait for the browser's seek event with a finite limit.
  await next.webContents.executeJavaScript(`(async()=>{const a=${MEDIA};if(!a)throw Error('FLOW_UNAVAILABLE');
   await new Promise((resolve,reject)=>{let timer;
    const finish=error=>{clearTimeout(timer);a.removeEventListener('seeked',done);a.removeEventListener('error',failed);error?reject(error):resolve();};
    const done=()=>finish(),failed=()=>finish(Error('FLOW_NOT_READY'));
    a.addEventListener('seeked',done);a.addEventListener('error',failed);
    timer=setTimeout(failed,2400);
    try{a.currentTime=0;if(!a.seeking)done();}catch(e){finish(e);}
   });return true;})()`);
  if(generation!==this.generation)throw Error('FLOW_CANCELLED');
  let startAt=Math.max(Date.now()+180,notBefore),firstBeat=0;
  if(plan){
   const oldPhase=oldInfo.wall+(a.phase-oldInfo.outputContext)*1000;
   // HTML's media clock follows audible output, not the context's render-ahead
   // clock. Using currentTime here would shift the entry by output latency.
   const mediaPhase=incoming.mediaTime+(b.phase-incoming.outputContext)*incoming.rate;
   firstBeat=((mediaPhase%b.period)+b.period)%b.period/plan.rate;
   const period=a.period*1000,minBeat=Math.max(Date.now()+400,notBefore)+firstBeat*1000;
   const target=oldPhase+Math.ceil((minBeat-oldPhase)/period)*period;
   startAt=target-firstBeat*1000;
  }
  await next.webContents.executeJavaScript(`(async()=>{const a=${MEDIA};if(!a)throw Error('FLOW_UNAVAILABLE');
   if(window.__emberFlowAudio)window.__emberFlowAudio.points.length=0;
   a.preservesPitch=true;a.playbackRate=${plan?.rate||1};
   await new Promise(r=>setTimeout(r,Math.max(0,${startAt}-Date.now())));
   await a.play();return true;})()`);
  if(generation!==this.generation)throw Error('FLOW_CANCELLED');
  return plan?{...plan,firstBeat,aligned:true}:null;
 }
 async restoreRate(win,rate,duration,startsAt=Date.now()){
  if(Math.abs(rate-1)<.0001)return;
  await win.webContents.executeJavaScript(`(()=>{const a=${MEDIA};if(!a)return;
   const start=performance.now()+(${Number(startsAt)}-Date.now());
   clearInterval(window.__emberFlowRateTimer);window.__emberFlowRateTimer=setInterval(()=>{
    const x=Math.max(0,Math.min(1,(performance.now()-start)/(${duration}*1000))),ease=x*x*(3-2*x);
    const rate=${rate}+(1-${rate})*ease;if(x>0&&Math.abs(a.playbackRate-rate)>.0001){a.preservesPitch=true;a.playbackRate=rate;}
    if(x>=1)clearInterval(window.__emberFlowRateTimer);
   },40);})()`);
 }
 async transition(p){
  if(!this.next||this.key!==p.key)throw Error('FLOW_NOT_READY');
  const generation=this.generation,old=this.current,next=this.next;
  try{
   this.pendingState=await this.request(old,{method:'status'});
   if(this.pendingState.duration-this.pendingState.position>23)throw Error('FLOW_NOT_READY');
   next.webContents.setBackgroundThrottling?.(false);
   const initial=await this.inspect(old);this.tailStartTime=initial?.time||0;
   const analyze=this.beatSync;
   await this.holdTail(old);await this.startMuted(next,analyze);
   const deadline=Date.now()+4200;let startupTimer;
   try{await Promise.race([this.request(next,{method:'transport',params:{action:'resume'}}),
    new Promise((_,reject)=>{startupTimer=setTimeout(()=>reject(Error('FLOW_NOT_READY')),3500);})]);}
   finally{clearTimeout(startupTimer);}
   let b;const until=Math.min(deadline,Date.now()+2500);
   do{if(generation!==this.generation)throw Error('FLOW_CANCELLED');b=await this.inspect(next);
    if(b?.playing&&b.time>.01)break;await new Promise(r=>setTimeout(r,40));}while(Date.now()<until);
   let beatPlan=null;
   if(analyze){
    const end=Date.now()+6000;
    while(Date.now()<end){if(generation!==this.generation)throw Error('FLOW_CANCELLED');await new Promise(r=>setTimeout(r,100));}
    const oldState=await this.inspect(old),left=this.pendingState.duration-this.pendingState.position-(oldState.time-this.tailStartTime);
    const notBefore=Date.now()+Math.max(0,left-Math.min(8,Number(p.duration)||8)-.35)*1000;
    beatPlan=await this.align(next,await this.rhythm(old),await this.rhythm(next),generation,notBefore);
   }
   const a=await this.inspect(old);
   if(generation!==this.generation)throw Error('FLOW_CANCELLED');
   if(!a||!b?.playing)throw Error('FLOW_UNAVAILABLE');
   const remaining=this.pendingState.duration-this.pendingState.position-(a.time-this.tailStartTime)-.1;
   const duration=a.playing?Math.max(.15,Math.min(8,Number(p.duration)||8,remaining)):.15;
   const startsAt=Date.now()+250;
   await Promise.all([this.gain(old,0,duration,1,startsAt),this.gain(next,1,duration,0,startsAt)]);
   if(generation!==this.generation)throw Error('FLOW_CANCELLED');
   const recovery=beatPlan?Math.max(1.5,Math.min(3.5,240/beatPlan.bpm)):0;
   if(beatPlan)await this.restoreRate(next,beatPlan.rate,recovery,startsAt+duration*1000);
   this.current=next;this.next=null;this.old=old;this.key='';this.pendingState=null;
   this.timer=setTimeout(()=>{this.timer=null;
    if(!old.isDestroyed())old.destroy();if(this.old===old)this.old=null;
    if(this.current===next&&!next.isDestroyed()){
     if(recovery){next.webContents.executeJavaScript('window.__emberFlowAudio?.stop();true').catch(()=>{});
      this.timer=setTimeout(()=>{this.timer=null;if(this.current===next&&!next.isDestroyed())next.webContents.executeJavaScript(RELEASE).catch(()=>{});},recovery*1000);
     }else next.webContents.executeJavaScript(RELEASE).catch(()=>{});
    }
   },duration*1000+350);
   return {started:true,duration,overlap:a.playing,beatSync:beatPlan,recovery};
  }catch(e){
   if(generation===this.generation){await this.cancel();
    if(!old.isDestroyed()){
     const state=await this.inspect(old).catch(()=>null);
     if(state&&!state.ended&&!state.error)await this.request(old,{method:'transport',params:{action:'resume'}}).catch(()=>{});}}
   throw e;
  }
 }
 async status(){
  if(!this.pendingState)return null;const a=await this.inspect(this.current);
  return a?{...this.pendingState,playing:a.playing,position:this.pendingState.position+a.time-this.tailStartTime}:null;
 }
 async command(p){
  if(p.operation==='prepare')return this.prepare(p);
  if(p.operation==='transition')return this.transition(p);
  if(p.operation==='cancel'){await this.cancel();return {stopped:true};}
  if(p.operation==='status')return {current:await this.inspect(this.current),outgoing:this.old?await this.inspect(this.old):null,
   rhythm:this.beatSync?detectBeat((await this.rhythm(this.current))?.points):null};
  throw Error('INVALID_ARGUMENTS');
 }
}
module.exports={FlowDecks,mixCurve};
