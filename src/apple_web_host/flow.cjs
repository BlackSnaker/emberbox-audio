'use strict';
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
 const a=window.__emberFlowMedia,base=window.__emberFlowVolume;
 if(a&&Number.isFinite(base)){delete a.volume;Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype,'volume').set.call(a,base);}
 if(a&&window.__emberFlowVolumeGuard)a.removeEventListener('volumechange',window.__emberFlowVolumeGuard,true);
 delete window.__emberFlowVolumeGuard;delete window.__emberFlowVolume;delete window.__emberFlowMultiplier;
 delete window.__emberFlowMedia;delete window.__emberFlowPlayer;})()`;

class FlowDecks {
 constructor(current,make,request,url){Object.assign(this,{current,make,request,url,next:null,old:null,timer:null,key:'',generation:0,pendingState:null});}
 async inspect(win){
  const s=await win.webContents.executeJavaScript(`(()=>{const a=${MEDIA};return a?{playing:!a.paused&&!a.ended,ended:a.ended,error:!!a.error,time:a.currentTime,volume:Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype,'volume').get.call(a)}:null;})()`);
  return s?{...s,audible:win.webContents.isCurrentlyAudible()}:null;
 }
 async gain(win,to,duration=0,from=to){return win.webContents.executeJavaScript(`(()=>{const a=${MEDIA};if(!a)throw Error('FLOW_UNAVAILABLE');
  const nativeVolume=Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype,'volume');
  if(window.__emberFlowVolume===undefined){window.__emberFlowVolume=a.volume;
    Object.defineProperty(a,'volume',{configurable:true,get(){return window.__emberFlowVolume;},set(v){window.__emberFlowVolume=v;nativeVolume.set.call(a,v*(window.__emberFlowMultiplier??1));}});}
  if(!window.__emberFlowVolumeGuard){window.__emberFlowVolumeGuard=e=>e.stopImmediatePropagation();a.addEventListener('volumechange',window.__emberFlowVolumeGuard,true);}
  clearInterval(window.__emberFlowTimer);
  const start=performance.now(),set=Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype,'volume').set;
  const step=()=>{let x=${duration}>0?Math.min(1,(performance.now()-start)/(${duration}*1000)):1;
   x=x*x*(3-2*x);window.__emberFlowMultiplier=${from}+(${to}-${from})*x;
   set.call(a,window.__emberFlowVolume*window.__emberFlowMultiplier);if(x>=1)clearInterval(window.__emberFlowTimer);};
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
  await this.cancel();const generation=this.generation,w=this.make(false);this.next=w;
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
   setTimeout(()=>{if(!released){release();a.pause();}},8000);return true;})()`);
 }
 async startMuted(win){
  await win.webContents.executeJavaScript(`(()=>{const proto=HTMLMediaElement.prototype,play=proto.play,
   volume=Object.getOwnPropertyDescriptor(proto,'volume');
   const release=()=>{if(proto.play===hook)proto.play=play;};
   const hook=function(){release();const a=this;window.__emberFlowMedia=a;window.__emberFlowVolume=a.volume;
    window.__emberFlowMultiplier=0;
    Object.defineProperty(a,'volume',{configurable:true,get(){return window.__emberFlowVolume;},set(v){
      window.__emberFlowVolume=v;volume.set.call(a,v*(window.__emberFlowMultiplier??1));}});
    window.__emberFlowVolumeGuard=e=>e.stopImmediatePropagation();a.addEventListener('volumechange',window.__emberFlowVolumeGuard,true);
    volume.set.call(a,0);return play.call(a);};
   proto.play=hook;window.__emberFlowRelease=release;setTimeout(release,4000);return true;})()`);
 }
 async transition(p){
  if(!this.next||this.key!==p.key)throw Error('FLOW_NOT_READY');
  const generation=this.generation,old=this.current,next=this.next;
  try{
   this.pendingState=await this.request(old,{method:'status'});
   next.webContents.setBackgroundThrottling?.(false);
   const initial=await this.inspect(old);this.tailStartTime=initial?.time||0;
   await this.holdTail(old);await this.startMuted(next);
   const deadline=Date.now()+4200;let startupTimer;
   try{await Promise.race([this.request(next,{method:'transport',params:{action:'resume'}}),
    new Promise((_,reject)=>{startupTimer=setTimeout(()=>reject(Error('FLOW_NOT_READY')),3500);})]);}
   finally{clearTimeout(startupTimer);}
   let b;const until=Math.min(deadline,Date.now()+2500);
   do{if(generation!==this.generation)throw Error('FLOW_CANCELLED');b=await this.inspect(next);
    if(b?.playing&&b.time>.01)break;await new Promise(r=>setTimeout(r,40));}while(Date.now()<until);
   const a=await this.inspect(old);
   if(generation!==this.generation)throw Error('FLOW_CANCELLED');
   if(!a||!b?.playing)throw Error('FLOW_UNAVAILABLE');
   const remaining=this.pendingState.duration-this.pendingState.position-(a.time-this.tailStartTime)-.1;
   const duration=a.playing?Math.max(.15,Math.min(6,Number(p.duration)||4,remaining)):.15;
   await Promise.all([this.gain(old,0,duration,1),this.gain(next,1,duration,0)]);
   this.current=next;this.next=null;this.old=old;this.key='';this.pendingState=null;
   this.timer=setTimeout(()=>{this.timer=null;
    if(!old.isDestroyed())old.destroy();if(this.old===old)this.old=null;
    if(this.current===next&&!next.isDestroyed())next.webContents.executeJavaScript(RELEASE).catch(()=>{});
   },duration*1000+80);
   return {started:true,duration,overlap:a.playing};
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
  if(p.operation==='status')return {current:await this.inspect(this.current),outgoing:this.old?await this.inspect(this.old):null};
  throw Error('INVALID_ARGUMENTS');
 }
}
module.exports={FlowDecks};
