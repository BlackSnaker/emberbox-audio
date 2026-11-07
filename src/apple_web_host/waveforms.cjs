'use strict';
const os=require('node:os');
// One disposable, low-priority licensed decoder. Only peak summaries leave it.
class Waveforms {
 constructor(owner){this.owner=owner;this.job=null;}
 cancel(key){
  const j=this.job;if(!j||key&&j.key!==key)return {cancelled:true};
  this.job=null;clearTimeout(j.timer);j.cancelled=true;
  if(j.child&&!j.child.killed)j.child.kill('SIGTERM');
  if(j.context)this.owner.source(j.win,{action:'close',contextId:j.context}).catch(()=>{});
  this.owner.source(j.win,{action:'cancel-prepare',requestKey:j.requestKey}).catch(()=>{});
  return {cancelled:true};
 }
 command(win,p,runtime){
  if(p.operation==='waveform-cancel')return this.cancel(p.key);
  if(p.operation==='waveform-status'){
   const j=this.job;return j&&j.key===p.key?{phase:j.phase,error:j.error||'',waveform:j.result||null}:{phase:'cancelled'};
  }
  if(p.operation!=='waveform-start'||!['songs','library-songs'].includes(p.kind)||!/^\w[\w.-]{0,199}$/.test(String(p.id))||
   typeof p.key!=='string'||!/^[a-f0-9]{32}$/.test(p.key)||!['out','in'].includes(p.role)||!Number.isFinite(p.seconds)||p.seconds<1||p.seconds>64)throw Error('INVALID_ARGUMENTS');
  if(!runtime)throw Error('SPATIAL_SETUP_REQUIRED');
  const o=this.owner;if(o.session?.manual||o.session?.transition||o.session?.seeking)throw Error('SPATIAL_BUSY');
  this.cancel();const j={win,key:p.key,requestKey:'native-'+(++o.generation),phase:'preparing',cancelled:false};this.job=j;
  j.timer=setTimeout(()=>this.fail(j,'SPATIAL_NETWORK_TIMEOUT'),60000);
  this.run(j,p,runtime).catch(e=>this.fail(j,/^(SPATIAL_[A-Z_]+|SIGN_IN_REQUIRED|SUBSCRIPTION_REQUIRED|DEVICE_LIMIT)$/.test(e.message)?e.message:'SPATIAL_PLAYBACK_FAILED'));
  return {accepted:true};
 }
 alive(j){return this.job===j&&!j.cancelled;}
 fail(j,code){if(!this.alive(j))return;this.release(j);j.phase='error';j.error=code;}
 release(j){
  clearTimeout(j.timer);
  if(j.child&&!j.child.killed)j.child.kill('SIGTERM');
  if(j.context){const context=j.context;j.context=null;this.owner.source(j.win,{action:'close',contextId:context}).catch(()=>{});}
 }
 async run(j,p,runtime){
  const o=this.owner,prepared=await o.source(j.win,{action:'prepare',requestKey:j.requestKey,id:p.id,kind:p.kind,allowStereo:true,fairplay:!!runtime.fairplay,waveform:true});
  j.context=prepared.contextId;
  if(!this.alive(j)){this.release(j);return;}
  const duration=Number(prepared.metadata.duration);if(!Number.isFinite(duration)||duration<=0)throw Error('SPATIAL_SOURCE_UNSUPPORTED');
  const seconds=Math.min(p.seconds,duration),position=p.role==='out'?Math.max(0,duration-seconds):0;
  const rate=o.session?.rate||(runtime.fairplay?192000:48000);
  const child=j.child=o.spawn(process.env.EMBERBOX_SPATIAL_WORKER,['pipe','pipe','pipe','ignore'],rate);
  try{os.setPriority(child.pid,15);}catch{}
  j.phase='decoding';let bytes=0;
  o.wire(child,value=>{
   if(!this.alive(j))return;
   if(value.type==='request'){
    if(typeof value.id!=='string'||value.id.length>100||!['segment','license'].includes(value.action)||value.contextId&&value.contextId!==j.context){this.fail(j,'SPATIAL_SOURCE_INVALID');return;}
    const params=value.action==='license'?{index:value.index,challenge:value.challenge}:{index:value.index,offset:value.offset};
    o.source(j.win,{action:value.action,contextId:j.context,...params}).then(result=>{
     if(!this.alive(j))return;
     if(value.action==='segment')bytes+=Math.ceil((result.data?.length||0)*.75);
     if(bytes>160*1024*1024){this.fail(j,'SPATIAL_SOURCE_LIMIT');return;}
     o.send(child,{type:'response',id:value.id,result});
    }).catch(()=>{if(this.alive(j))o.send(child,{type:'response',id:value.id,error:'SPATIAL_NETWORK'});});
   }else if(value.type==='waveform'){
    const wave=value.waveform;
    if(!wave||wave.evidence!=='decoded-pcm'||!Array.isArray(wave.bins)||wave.bins.length<1||wave.bins.length>2049||
      !wave.bins.every(row=>Array.isArray(row)&&row.length===3&&row.every(Number.isFinite))){this.fail(j,'SPATIAL_SOURCE_INVALID');return;}
    j.result=wave;j.phase='ready';this.release(j);
   }else if(value.type==='error')this.fail(j,'SPATIAL_PLAYBACK_FAILED');
  },code=>this.fail(j,code));
  o.send(child,{type:'start',runtime,outputRate:rate,cdm:process.env.EMBERBOX_WIDEVINE,prepared,position,generation:1,
   scene:o.scenes.render(),waveform:{seconds}});
 }
}
module.exports={Waveforms};
