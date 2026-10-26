'use strict';
const fs=require('node:fs');
const path=require('node:path');
const {spawn}=require('node:child_process');
const source=fs.readFileSync(path.join(__dirname,'spatial_source.js'),'utf8');
const errors=new Set(['SIGN_IN_REQUIRED','SUBSCRIPTION_REQUIRED','DEVICE_LIMIT','INVALID_ARGUMENTS',
 'SPATIAL_NETWORK','SPATIAL_SOURCE_LIMIT','SPATIAL_SOURCE_UNSUPPORTED','SPATIAL_NO_ATMOS_ASSET',
 'SPATIAL_LICENSE_REJECTED','SPATIAL_STALE_CONTEXT','SPATIAL_BUSY']);
async function sourceRequest(win,params){
 if(!win||win.isDestroyed()||!win.webContents.getURL().startsWith('https://music.apple.com/'))throw Error('SIGN_IN_REQUIRED');
 const result=await win.webContents.executeJavaScript('(async()=>{'+source+';try{return {result:await emberboxSpatialSource('+JSON.stringify(params)+')}}catch(e){return {error:'+JSON.stringify([...errors])+'.includes(e.message)?e.message:"SPATIAL_SOURCE_UNSUPPORTED",appleStatus:Number.isInteger(e.appleStatus)?e.appleStatus:null}}})()');
 if(result.error){const error=Error(result.error);if(Number.isInteger(result.appleStatus))error.appleStatus=result.appleStatus;throw error;}return result.result;
}
function fairplayRuntime(){
 try{const r=JSON.parse(fs.readFileSync(process.env.EMBERBOX_FAIRPLAY_RUNTIME,'utf8'));
  return r.schema===1&&typeof r.library==='string'&&typeof r.librarySha256==='string'&&/^[a-f0-9]{64}$/.test(r.librarySha256)&&typeof r.profile==='string'&&fs.statSync(r.library).isFile()&&fs.statSync(path.join(r.profile,'session-ready')).isFile()?r:null;
 }catch{return null;}
}
function runtime(){
 try{const value=JSON.parse(fs.readFileSync(process.env.EMBERBOX_SPATIAL_RUNTIME,'utf8'));
  return value.schema===1&&['host','decoder'].every(k=>typeof value[k]==='string'&&fs.statSync(value[k]).isFile())?{...value,fairplay:fairplayRuntime()}:null;
 }catch{return null;}
}
class SpatialPlayback {
 constructor(page,cancelFlow){
  this.page=page;this.cancelFlow=cancelFlow;this.source=sourceRequest;this.session=null;
  this.blocked=new Set();this.error='';this.revision=0;this.generation=0;
  try{this.enabled=JSON.parse(fs.readFileSync(process.env.EMBERBOX_SPATIAL_CONFIG,'utf8')).enabled===true;}catch{this.enabled=false;}
 }
 info(){const r=this.session;return {enabled:this.enabled,available:!!runtime(),losslessAvailable:!!fairplayRuntime(),fastSwitch:true,phase:r?.state.phase||'idle',error:this.error,switching:!!r?.manual,switchError:this.switchError||null,
  flow:r&&(r.transition||!r.standby&&r.decks.filter(Boolean).length>1)?'mixing':r?.standby?.ready?'ready':r?.standby?'preparing':'idle',flowError:this.flowError||'',workerExit:this.workerExit||null,fragment:this.fragmentDebug||null,mix:this.mixDebug||null};}
 async configure(enabled){
  if(typeof enabled!=='boolean')throw Error('INVALID_ARGUMENTS');
  if(enabled&&!runtime())throw Error('SPATIAL_SETUP_REQUIRED');
  this.enabled=enabled;this.blocked.clear();this.error='';this.switchError=null;
  const file=process.env.EMBERBOX_SPATIAL_CONFIG;
  if(file){fs.mkdirSync(path.dirname(file),{recursive:true,mode:0o700});fs.writeFileSync(file+'.tmp',JSON.stringify({enabled}),{mode:0o600});fs.renameSync(file+'.tmp',file);}
  if(!enabled)await this.stop(true);return this.info();
 }
 matches(metadata,state){return String(metadata.id||'')===String(state.id||'')||!!metadata.catalogId&&String(metadata.catalogId)===String(state.catalogId||'');}
 merge(win,state){
  const id=String(state.id||state.catalogId||'');let r=this.session;
  if(r&&this.matches(r.active.metadata,state))r.synchronizing=false;
  // A paused MusicKit queue may retain the previous nowPlayingItem. The native
  // output owns its metadata until an explicit command or new web playback.
  if(r&&state.playing&&!this.matches(r.active.metadata,state)){this.stop(false).catch(()=>{});r=null;}
  if(!r&&this.enabled&&state.playing&&state.authorized&&id&&(state.availableFormats?.includes('dolby-atmos')||fairplayRuntime())&&!this.blocked.has(id)&&runtime()){
   this.begin(win,state);r=this.session;
  }
  return {...state,...(r?{...r.active.metadata,position:r.state.position,
   playing:r.paused?false:r.state.phase==='preparing'?true:r.state.playing,
   audioQuality:r.active.quality||state.audioQuality,ended:r.state.phase==='ended',emberFlow:!!r.active.quality&&r.state.phase!=='preparing',emberBeatSync:false}:{}),spatial:this.info()};
 }
 begin(win,metadata,position=metadata.position,paused=false){
  const deck={metadata:{...metadata},slot:0,generation:++this.generation,quality:null,ready:false,context:null,child:null};
  const nativeRuntime=runtime();
  const r={win,nativeRuntime,rate:nativeRuntime?.fairplay?192000:48000,active:deck,decks:[deck,null],standby:null,mixer:null,paused,
   state:{phase:'preparing',position:Number(position)||0,playing:!paused},lastAdvance:Date.now(),flowRevision:0,preparation:Promise.resolve()};
  this.session=r;this.error='';this.switchError=null;this.workerHint='';this.workerExit=null;this.fragmentDebug=null;
  this.blocked.add(String(metadata.id));if(this.blocked.size>32)this.blocked.delete(this.blocked.values().next().value);
  r.stall=setInterval(()=>{if(this.session===r&&r.active.quality&&!r.paused&&r.state.phase!=='ended'&&Date.now()-r.lastAdvance>15000)this.failed(r,'SPATIAL_BUFFER_TIMEOUT');},1000);
  r.watchdog=setTimeout(()=>{if(this.session===r&&!r.active.quality)this.failed(r,'SPATIAL_START_TIMEOUT');},25000);
  this.load(r).catch(e=>this.failed(r,errors.has(e.message)?e.message:'SPATIAL_PLAYBACK_FAILED'));
 }
 spawn(file,stdio,rate=48000){return spawn(process.env.EMBERBOX_SPATIAL_PYTHON,[file],{stdio,
  env:{...process.env,PYTHONUNBUFFERED:'1',PYTHONFAULTHANDLER:'1',EMBERBOX_SPATIAL_RATE:String(rate),RAYON_NUM_THREADS:'2',OMP_NUM_THREADS:'1'}});}
 wire(child,message,failed){
  child.stdin.on('error',()=>{});child.on('error',()=>failed('SPATIAL_WORKER_UNAVAILABLE'));
  child.stderr.on('data',chunk=>{const text=chunk.toString('utf8');
   const frame=[...text.matchAll(/File "[^"\n]*\/(spatial_[a-z_]+\.py)", line (\d+) in ([A-Za-z_]+)/g)].pop();
   if(frame)this.workerHint=frame[1]+':'+frame[2]+':'+frame[3];else if(text.includes('ModuleNotFoundError'))this.workerHint='python-module-missing';});
  child.on('exit',(code,signal)=>{if(child.killed)return;this.workerExit={code:Number.isInteger(code)?code:null,signal:['SIGSEGV','SIGABRT','SIGSYS','SIGKILL'].includes(signal)?signal:null,hint:this.workerHint||''};failed('SPATIAL_WORKER_EXIT');});
  let buffer='';child.stdout.on('data',chunk=>{
   buffer+=chunk.toString('utf8');if(buffer.length>2*1024*1024){failed('SPATIAL_WORKER_PROTOCOL');return;}
   let index;while((index=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,index);buffer=buffer.slice(index+1);
    let value;try{value=JSON.parse(line);}catch{failed('SPATIAL_WORKER_PROTOCOL');return;}message(value);}
  });
 }
 send(child,value){if(child&&!child.killed&&child.stdin.writable)child.stdin.write(JSON.stringify(value)+'\n');}
 pipePcm(r,deck,child){
  const source=child.stdio[3],input=r.mixer.stdio[3+deck.slot];let buffer=Buffer.alloc(0),waiting=false,closed=false;
  const drain=()=>{waiting=false;flush();if(!waiting&&!closed)source.resume();};
  const flush=()=>{
   while(!closed&&!waiting&&buffer.length>=8){
    const generation=buffer.readUInt32LE(0),length=buffer.readUInt32LE(4);
    if(generation!==deck.generation||length<8||length>1048576||length%8){this.deckFailed(r,deck,'SPATIAL_PCM_FORMAT');return;}
    if(buffer.length<length+8)return;
    const frame=buffer.subarray(0,length+8);buffer=buffer.subarray(length+8);
    // A cancelled producer may end halfway through a frame. Forward complete
    // frames only, so its replacement cannot corrupt the shared slot's pipe.
    if(!input.write(frame)){waiting=true;source.pause();input.once('drain',drain);}
   }
  };
  const data=chunk=>{if(closed)return;buffer=buffer.length?Buffer.concat([buffer,chunk]):chunk;flush();};
  source.on('data',data);
  deck.closePcm=()=>{closed=true;buffer=Buffer.alloc(0);source.off('data',data);source.pause();input.off('drain',drain);};
 }
 async load(r){
  await this.cancelFlow();if(this.session!==r)return;
  await this.page(r.win,{method:'transport',params:{action:'pause'}});if(this.session!==r)return;
  const mixer=r.mixer=this.spawn(path.join(path.dirname(process.env.EMBERBOX_SPATIAL_WORKER),'spatial_mixer.py'),['pipe','pipe','pipe','pipe','pipe'],r.rate);
  for(const input of mixer.stdio.slice(3))input.on('error',()=>{});
  this.wire(mixer,v=>this.mixerMessage(r,v),code=>this.failed(r,code));
  this.send(mixer,{type:'pause',paused:r.paused});
  const metadata=r.active.metadata,id=/^\d{1,20}$/.test(String(metadata.catalogId||''))?metadata.catalogId:metadata.id;
  await this.loadDeck(r,r.active,await this.source(r.win,{action:'prepare',id,kind:String(id).startsWith('i.')?'library-songs':'songs',allowStereo:true,fairplay:!!r.nativeRuntime?.fairplay}),r.state.position);
 }
 async loadDeck(r,deck,prepared,position=0){
  deck.context=prepared.contextId;
  if(this.session!==r||!r.decks.includes(deck)){this.source(r.win,{action:'close',contextId:deck.context}).catch(()=>{});return;}
  this.send(r.mixer,{type:'slot',slot:deck.slot,generation:deck.generation,position,preroll:deck.manual?.4:2});
  const child=deck.child=this.spawn(process.env.EMBERBOX_SPATIAL_WORKER,['pipe','pipe','pipe','pipe'],r.rate);
  this.wire(child,v=>this.message(r,deck,v),code=>this.deckFailed(r,deck,code));
  this.pipePcm(r,deck,child);
  this.send(child,{type:'start',runtime:r.nativeRuntime,outputRate:r.rate,cdm:process.env.EMBERBOX_WIDEVINE,prepared,position,pcm:true,generation:deck.generation});
 }
 message(r,deck,value){
  if(this.session!==r||!r.decks.includes(deck))return;
  if(value.type==='request'){
   if(typeof value.id!=='string'||value.id.length>100||!['license','segment'].includes(value.action))return;
   const params=value.action==='license'?{index:value.index,challenge:value.challenge}:{index:value.index,offset:value.offset};
   this.source(r.win,{action:value.action,contextId:deck.context,...params}).then(result=>{
    if(this.session===r&&r.decks.includes(deck)){
     if(value.action==='segment'&&deck===r.active)this.fragmentDebug={index:value.index,total:result.total,initBytes:result.initBytes,originalOffset:result.originalOffset};
     this.send(deck.child,{type:'response',id:value.id,result});}
   }).catch(e=>{
    if(Number.isInteger(e.appleStatus))this.fragmentDebug={...this.fragmentDebug,licenseStatus:e.appleStatus};
    this.send(deck.child,{type:'response',id:value.id,error:errors.has(e.message)?e.message:'SPATIAL_SOURCE_UNSUPPORTED'});
   });
  }else if(value.type==='quality'){
   const q=value.audioQuality;
   if(q?.codec==='eac3'&&q.variant==='dolby-atmos'&&q.evidence==='decoder'&&q.renderer==='openjoc-binaural'&&q.sampleRate===48000&&q.channels===2&&(q.outputSampleRate===undefined||q.outputSampleRate===r.rate)){
    deck.quality={codec:'eac3',variant:'dolby-atmos',evidence:'decoder',renderer:'openjoc-binaural',sampleRate:48000,channels:2,...(r.rate!==48000?{outputSampleRate:r.rate}:{})};
    if(deck===r.active){clearTimeout(r.watchdog);r.lastAdvance=Date.now();}
   }else if(q?.codec==='aac'&&q.evidence==='decoder'&&[44100,48000,32000,24000].includes(q.sampleRate)&&q.outputSampleRate===r.rate&&q.channels===2){
    deck.quality={codec:'aac',evidence:'decoder',sampleRate:q.sampleRate,channels:2,outputSampleRate:r.rate};
    if(deck===r.active){clearTimeout(r.watchdog);r.lastAdvance=Date.now();}
   }else if(q?.codec==='alac'&&q.evidence==='decoder'&&[44100,48000,88200,96000,176400,192000].includes(q.sampleRate)&&[16,20,24].includes(q.bitDepth)&&q.outputSampleRate===r.rate&&q.channels===2&&r.nativeRuntime?.fairplay){
    deck.quality={codec:'alac',evidence:'decoder',sampleRate:q.sampleRate,bitDepth:q.bitDepth,channels:2,outputSampleRate:r.rate};
    if(deck===r.active){clearTimeout(r.watchdog);r.lastAdvance=Date.now();}
   }
  }else if(value.type==='decoded-end'){
   if(Number.isSafeInteger(value.frames)&&value.frames>=0)this.send(r.mixer,{type:'end',slot:deck.slot,generation:deck.generation,frames:value.frames});
  }else if(value.type==='error'){
   if(/^[A-Za-z -]{1,90}$/.test(value.hint||''))this.fragmentDebug={...this.fragmentDebug,hint:value.hint};
   const diagnostic=value.diagnostics;
   if(diagnostic&&['certificate','generate','update'].includes(diagnostic.stage)&&Number.isInteger(diagnostic.exception)&&diagnostic.exception>=0&&diagnostic.exception<=4)this.fragmentDebug={...this.fragmentDebug,cdm:diagnostic};
   this.deckFailed(r,deck,/^(?:SPATIAL_[A-Z_]+|DEVICE_LIMIT|SUBSCRIPTION_REQUIRED|SIGN_IN_REQUIRED)$/.test(value.code||'')?value.code:'SPATIAL_PLAYBACK_FAILED');
  }
 }
 mixerMessage(r,value){
  if(this.session!==r)return;
  const deck=r.decks[value.slot];
  if(value.type==='ready'&&deck?.generation===value.generation)deck.ready=true;
  else if(value.type==='state'&&deck===r.active){
   if(Array.isArray(value.buffers))this.mixDebug={buffers:value.buffers.slice(0,2).map(row=>Array.isArray(row)?row.slice(0,4).map(v=>Number.isSafeInteger(v)?v:0):[]),frame:Number.isSafeInteger(value.mixFrame)?value.mixFrame:0,fade:Array.isArray(value.fade)?value.fade.slice(0,2).map(v=>Number.isSafeInteger(v)?v:0):[]};
   if(Number.isFinite(value.position)&&value.position>=0&&value.position<=Number(deck.metadata.duration||0)+1){
    if(value.position>r.state.position+.05)r.lastAdvance=Date.now();r.state.position=value.position;}
   if(['preparing','playing','ended'].includes(value.phase))r.state.phase=value.phase;
   r.state.playing=value.playing===true;
  }else if(value.type==='flow-started'&&deck&&deck===r.standby&&r.transition?.key===value.key){
   this.blocked.add(String(deck.metadata.id));if(this.blocked.size>32)this.blocked.delete(this.blocked.values().next().value);
   r.active=deck;r.standby=null;r.synchronizing=true;r.state={phase:'playing',position:deck.position||0,playing:!r.paused};r.lastAdvance=Date.now();
   const pending=r.transition;r.transition=null;clearTimeout(pending?.timer);
   if(r.manual===pending?.manual)r.manual=null;
   pending?.resolve({started:true,duration:Math.min(8,Number(value.duration)||8),overlap:true,beatSync:null,recovery:0});
   // Keep the website's metadata in step without setQueue/play: that would
   // start a second AAC/DRM pipeline just to describe our existing PCM output.
   this.page(r.win,{method:'play',params:{kind:deck.kind,id:deck.requestedId,native:true,metadata:deck.metadata}}).catch(()=>{});
  }else if(value.type==='released'&&deck?.generation===value.generation&&deck!==r.active)this.dropDeck(r,deck);
  else if(value.type==='error'){
   if(/^[A-Za-z _-]{1,60}$/.test(value.hint||''))this.mixDebug={...this.mixDebug,lastError:value.hint};
   this.failed(r,'SPATIAL_MIX_FAILED');
  }
 }
 deckFailed(r,deck,code){
  if(this.session!==r||!r.decks.includes(deck))return;
  if(deck===r.active||r.transition){this.failed(r,code);return;}
  deck.error=code;this.flowError=code;this.dropDeck(r,deck);this.send(r.mixer,{type:'cancel'});
 }
 dropDeck(r,deck){
  deck.closePcm?.();
  if(deck.child){deck.child.stdio[3]?.unpipe();this.send(deck.child,{type:'stop'});deck.child.kill('SIGTERM');}
  if(deck.context)this.source(r.win,{action:'close',contextId:deck.context}).catch(()=>{});
  if(r.standby===deck)r.standby=null;if(r.decks[deck.slot]===deck)r.decks[deck.slot]=null;
 }
 async prepareDeck(r,p,position=0,manual=false){
  const revision=r.flowRevision;
  const deck={metadata:{id:p.id},kind:p.kind,requestedId:p.id,key:p.key,position,manual,
   slot:1-r.active.slot,generation:++this.generation,quality:null,ready:false};
  r.standby=deck;
  // Only source negotiation is serialized. It must not create a third lease
  // when an obsolete click or an earlier automatic preload is still in flight.
  const prepare=async()=>{
   if(this.session!==r||revision!==r.flowRevision||r.standby!==deck)throw Error('FLOW_CANCELLED');
   const freeUntil=Date.now()+2000;
   while(r.decks[deck.slot]&&Date.now()<freeUntil)await new Promise(resolve=>setTimeout(resolve,20));
   if(this.session!==r||revision!==r.flowRevision||r.standby!==deck)throw Error('FLOW_CANCELLED');
   if(r.decks[deck.slot])throw Error('FLOW_NOT_READY');
   r.decks[deck.slot]=deck;
   const prepared=await this.source(r.win,{action:'prepare',id:p.id,kind:p.kind,allowStereo:true,fairplay:!!r.nativeRuntime?.fairplay});
   if(this.session!==r||revision!==r.flowRevision||r.standby!==deck){
    await this.source(r.win,{action:'close',contextId:prepared.contextId}).catch(()=>{});throw Error('FLOW_CANCELLED');}
   deck.metadata=prepared.metadata;
   await this.loadDeck(r,deck,prepared,position);
   return deck;
  };
  deck.loading=r.preparation.catch(()=>{}).then(prepare).catch(error=>{
   if(r.standby===deck)this.dropDeck(r,deck);
   throw error;
  });
  r.preparation=deck.loading.catch(()=>{});
  return deck.loading;
 }
 async waitReady(r,deck,valid,timeout=14000){
  const until=Date.now()+timeout;
  while(this.session===r&&r.standby===deck&&valid()&&!deck.error&&Date.now()<until){
   if(deck.ready&&deck.quality)return;
   await new Promise(resolve=>setTimeout(resolve,20));
  }
  if(!valid()||this.session!==r||r.standby!==deck)throw Error('FLOW_CANCELLED');
  throw Error(deck.error||'FLOW_NOT_READY');
 }
 select(r,p,position=0){
  const request={id:p.id,kind:p.kind,position};r.manual=request;this.error='';this.switchError=null;
  // Finish a cancelled overlap before reusing its slot. A new Play command
  // may arrive while that output clock is paused.
  if(r.paused&&r.decks.filter(Boolean).length>1){r.paused=false;this.send(r.mixer,{type:'pause',paused:false});}
  const reusable=r.standby&&!r.transition&&position===0&&
   (r.standby.requestedId===p.id||this.matches(r.standby.metadata,{id:p.id,catalogId:p.id}))?r.standby:null;
  r.manualTask=(async()=>{
   let deck=reusable;
   if(!deck){
    await this.flow(r,{operation:'cancel',force:true});
    if(r.manual!==request||this.session!==r)return;
    deck=await this.prepareDeck(r,{...p,key:'manual-'+(++this.generation)},position,true);
   }else if(deck.loading)await deck.loading;
   const valid=()=>r.manual===request;
   await this.waitReady(r,deck,valid,20000);
   if(!valid()||this.session!==r)return;
   r.paused=false;this.send(r.mixer,{type:'pause',paused:false});
   await new Promise((resolve,reject)=>{
    r.transition={key:deck.key,manual:request,resolve,reject,timer:setTimeout(()=>this.failed(r,'SPATIAL_MIX_TIMEOUT'),6000)};
    this.send(r.mixer,{type:'transition',key:deck.key,duration:.22,manual:true});
   });
  })().catch(error=>{
   if(this.session!==r||r.manual!==request)return;
   r.manual=null;this.switchError={id:request.id,code:errors.has(error.message)?error.message:'SPATIAL_SWITCH_FAILED'};
   if(r.standby)this.dropDeck(r,r.standby);
  });
  return {ok:true,preparing:!reusable?.ready};
 }
 async flow(r,p){
  if(p.operation==='cancel'){
   if(r.manual&&!p.force)return {cancelled:true};
   if(p.preserve&&!r.transition)return {cancelled:true};
   r.flowRevision++;const mixing=!!r.transition;clearTimeout(r.transition?.timer);r.transition?.reject(Error('FLOW_CANCELLED'));r.transition=null;
   if(r.standby){if(!mixing)this.dropDeck(r,r.standby);else r.standby=null;}
   this.send(r.mixer,{type:'cancel',keep:r.active.slot});return {cancelled:true};
  }
  if(p.operation==='status')return {current:{playing:!r.paused,time:r.state.position,rate:1},outgoing:r.decks.filter(Boolean).length>1?{playing:!r.paused}:null,rhythm:null};
  if(p.operation==='prepare'){
   this.flowError='';
   if(!r.mixer||!r.active.quality||r.manual||r.paused||r.state.phase!=='playing')throw Error('FLOW_NOT_READY');
   if(!['songs','library-songs'].includes(p.kind)||!/^\w[\w.-]{0,199}$/.test(String(p.id))||typeof p.key!=='string'||p.key.length>80)throw Error('INVALID_ARGUMENTS');
   await this.flow(r,{operation:'cancel'});const revision=r.flowRevision;
   let deck;
   try{
    deck=await this.prepareDeck(r,p);
    await this.waitReady(r,deck,()=>revision===r.flowRevision);return {ready:true};
   }catch(e){if(deck&&r.standby===deck)this.dropDeck(r,deck);throw e;}
  }
  if(p.operation==='transition'){
   const deck=r.standby;if(!deck?.ready||!deck.quality||deck.key!==p.key||r.transition||r.paused||r.active.metadata.duration-r.state.position>23)throw Error('FLOW_NOT_READY');
   const requested=Math.max(.15,Math.min(8,Number(p.duration)||8)),revision=r.flowRevision,until=Date.now()+14000;
   while(r.active.metadata.duration-r.state.position>requested+.65&&Date.now()<until){
    if(this.session!==r||revision!==r.flowRevision||r.paused)throw Error('FLOW_CANCELLED');
    await new Promise(resolve=>setTimeout(resolve,40));
   }
   if(this.session!==r||revision!==r.flowRevision||r.paused||r.standby!==deck)throw Error('FLOW_CANCELLED');
   if(r.active.metadata.duration-r.state.position>requested+1)throw Error('FLOW_NOT_READY');
   const duration=Math.max(.15,Math.min(requested,r.active.metadata.duration-r.state.position-.4));
   return new Promise((resolve,reject)=>{r.transition={key:p.key,resolve,reject,timer:setTimeout(()=>this.failed(r,'SPATIAL_MIX_TIMEOUT'),6000)};this.send(r.mixer,{type:'transition',key:p.key,duration});});
  }
  throw Error('INVALID_ARGUMENTS');
 }
 async failed(r,code){if(this.session!==r)return;this.error=code;await this.stop(true).catch(()=>{});}
 async restore(r,revision){
  if(r.win.isDestroyed())return;const deck=r.active,current=await this.page(r.win,{method:'status',params:{}});
  if(revision!==this.revision||this.session||current.playing&&!r.synchronizing&&!this.matches(deck.metadata,current))return;
  const id=/^\d{1,20}$/.test(String(deck.metadata.catalogId||''))?deck.metadata.catalogId:deck.metadata.id;
  await this.page(r.win,{method:'play',params:{kind:String(id).startsWith('i.')?'library-songs':'songs',id,
   position:r.state.position,paused:r.paused||r.state.phase==='ended'}});
 }
 async stop(restore=false){
  const r=this.session;if(!r)return;this.session=null;const revision=++this.revision;
  clearTimeout(r.watchdog);clearInterval(r.stall);r.flowRevision++;
  clearTimeout(r.transition?.timer);r.transition?.reject(Error('FLOW_CANCELLED'));r.transition=null;
  for(const deck of [...r.decks])if(deck)this.dropDeck(r,deck);
  if(r.mixer){this.send(r.mixer,{type:'stop'});r.mixer.kill('SIGTERM');}
  if(restore)await this.restore(r,revision);
 }
 async intercept(win,request){
  if(request.method==='spatial'&&request.params?.operation==='formats')return this.source(win,{action:'inspect',id:request.params.id,kind:request.params.kind,enhanced:request.params.enhanced,extended:request.params.extended,encryption:request.params.encryption,fairplayMetadata:request.params.fairplayMetadata});
  if(['play','transport','seek','enable','spatial'].includes(request.method))this.revision++;
  if(request.method==='spatial')return this.configure(request.params?.enabled);
  const r=this.session;if(!r)return null;
  if(request.method==='flow')return this.flow(r,request.params||{});
  if(request.method==='seek'){
   const position=Number(request.params?.position);if(!Number.isFinite(position)||position<0)throw Error('INVALID_ARGUMENTS');
   const metadata=r.active.metadata,target=Math.min(position,Number(metadata.duration)||position);
   if(!r.paused&&r.mixer&&r.active.quality)return this.select(r,{kind:String(metadata.id).startsWith('i.')?'library-songs':'songs',id:String(metadata.id)},target);
   await this.stop(false);this.begin(r.win,metadata,target,r.paused);return {ok:true};
  }
  if(request.method==='play'&&['songs','library-songs'].includes(request.params?.kind)&&/^\w[\w.-]{0,199}$/.test(String(request.params?.id))&&request.params?.paused!==true&&r.mixer&&r.active.quality){
   return this.select(r,{kind:request.params.kind,id:String(request.params.id)},Math.max(0,Number(request.params.position)||0));
  }
  if(request.method==='transport'&&['pause','resume','toggle'].includes(request.params?.action)){
   r.paused=request.params.action==='toggle'?!r.paused:request.params.action==='pause';r.state.playing=!r.paused;r.lastAdvance=Date.now();
   if(r.paused&&r.manual){r.manual=null;await this.flow(r,{operation:'cancel',force:true});}
   if(!r.paused&&r.state.phase==='ended'){const metadata=r.active.metadata;await this.stop(false);this.begin(r.win,metadata,0,false);}
   else this.send(r.mixer,{type:'pause',paused:r.paused});return {ok:true};
  }
  if(request.method==='play'||request.method==='transport'||request.method==='enable'&&request.params?.enabled!==true){
   const resume=request.method==='transport'&&!r.paused;const old=r.active.metadata.id;await this.stop(false);
   if(request.method==='play')this.blocked.delete(String(old));if(resume)this.resumeAfterTransport=true;
  }
  return null;
 }
 async after(win,request){if(this.resumeAfterTransport&&request.method==='transport'){
  this.resumeAfterTransport=false;await this.page(win,{method:'transport',params:{action:'resume'}});
 }}
}
module.exports={SpatialPlayback,sourceRequest};
