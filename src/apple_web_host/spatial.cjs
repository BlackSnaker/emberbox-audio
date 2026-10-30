'use strict';
const fs=require('node:fs');
const path=require('node:path');
const {spawn}=require('node:child_process');
const {Scenes,signature}=require('./scene.cjs');
const source=fs.readFileSync(path.join(__dirname,'spatial_source.js'),'utf8');
const errors=new Set(['SIGN_IN_REQUIRED','SUBSCRIPTION_REQUIRED','DEVICE_LIMIT','INVALID_ARGUMENTS',
 'SPATIAL_NETWORK','SPATIAL_SOURCE_LIMIT','SPATIAL_SOURCE_UNSUPPORTED','SPATIAL_NO_ATMOS_ASSET',
 'SPATIAL_LICENSE_REJECTED','SPATIAL_STALE_CONTEXT','SPATIAL_BUSY','SPATIAL_CANCELLED']);
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
  this.scenes=new Scenes(process.env.EMBERBOX_SPATIAL_CONFIG);this.enabled=this.scenes.enabled;
 }
 info(){const r=this.session;return {enabled:this.enabled,available:!!runtime(),losslessAvailable:!!fairplayRuntime(),fastSwitch:true,fastSeek:true,seeking:!!r?.seeking,seekStage:r?.active.seekStage||'',phase:r?.state.phase||'idle',error:this.error,switching:!!r?.manual,switchError:this.switchError||null,
  flow:r&&(r.transition||!r.standby&&r.decks.filter(Boolean).length>1)?'mixing':r?.standby?.ready?'ready':r?.standby?'preparing':'idle',flowError:this.flowError||'',workerExit:this.workerExit||null,fragment:this.fragmentDebug||null,mix:this.mixDebug||null,switchTiming:this.switchTiming||null,
  scene:{...this.scenes.snapshot(),headphoneStatus:r?.headphoneStatus||null,changing:!!(r?.scenePending||r?.seeking)}};}
 async configure(enabled){
  if(typeof enabled!=='boolean')throw Error('INVALID_ARGUMENTS');
  if(enabled&&!runtime())throw Error('SPATIAL_SETUP_REQUIRED');
  this.enabled=enabled;this.blocked.clear();this.error='';this.switchError=null;
  this.scenes.save(enabled);
  if(!enabled)await this.stop(true);return this.info();
 }
 matches(metadata,state){return String(metadata.id||'')===String(state.id||'')||!!metadata.catalogId&&String(metadata.catalogId)===String(state.catalogId||'');}
 applyScene(){
  const r=this.session;if(!r)return;
  const scene=this.scenes.render();
  this.applyHeadphones(r,scene);
  if(r.active.scene&&signature(r.active.scene)===signature(scene)){r.scenePending=false;return;}
  if(r.manual||r.transition||r.seeking||!r.active.quality){r.scenePending=true;return;}
  r.scenePending=false;
  this.flow(r,{operation:'cancel',force:true}).catch(()=>{});
  if(r.active.quality.variant==='dolby-atmos')this.seek(r,r.state.position);
  else r.active.scene=scene; // Stereo geometry stays intact; voicing lives in the shared mixer.
 }
 applyHeadphones(r,scene=this.scenes.render()){
  const key=JSON.stringify([scene.mode,scene.headphones]);
  if(!r.mixer||r.headphoneKey===key)return;
  r.headphoneKey=key;this.send(r.mixer,{type:'headphones',scene});
 }
 merge(win,state){
  const id=String(state.id||state.catalogId||'');let r=this.session;
  if(r?.scenePending)this.applyScene();
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
  const deck={metadata:{...metadata},slot:0,generation:++this.generation,requestKey:'native-'+(++this.generation),scene:this.scenes.render(),quality:null,ready:false,context:null,child:null};
  const nativeRuntime=runtime();
  const r={win,nativeRuntime,rate:nativeRuntime?.fairplay?192000:48000,active:deck,decks:[deck,null],standby:null,mixer:null,paused,
   state:{phase:'preparing',position:Number(position)||0,playing:!paused},lastAdvance:Date.now(),flowRevision:0,preparation:Promise.resolve(),idle:[null,null]};
  this.session=r;this.error='';this.switchError=null;this.workerHint='';this.workerExit=null;this.fragmentDebug=null;
  this.blocked.add(String(metadata.id));if(this.blocked.size>32)this.blocked.delete(this.blocked.values().next().value);
  r.stall=setInterval(()=>{if(this.session===r&&r.active.quality&&!r.paused&&r.state.phase!=='ended'&&Date.now()-r.lastAdvance>15000)this.failed(r,'SPATIAL_BUFFER_TIMEOUT');},1000);
  r.watchdog=setTimeout(()=>{if(this.session===r&&!r.active.quality)this.failed(r,'SPATIAL_START_TIMEOUT');},25000);
  this.load(r).catch(e=>this.failed(r,errors.has(e.message)?e.message:'SPATIAL_PLAYBACK_FAILED'));
 }
 spawn(file,stdio,rate=48000){return spawn(process.env.EMBERBOX_SPATIAL_PYTHON,[file],{stdio,
  env:{...process.env,PYTHONUNBUFFERED:'1',PYTHONFAULTHANDLER:'1',EMBERBOX_SPATIAL_RATE:String(rate),RAYON_NUM_THREADS:'2',OMP_NUM_THREADS:'1',OPENBLAS_NUM_THREADS:'1',MKL_NUM_THREADS:'1'}});}
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
 cancelPrime(keep){
  clearTimeout(this.primeTimer);this.primeTimer=null;
  const job=this.primeJob;
  if(job&&(!keep||job.id!==keep.id||job.kind!==keep.kind)){
   this.primeJob=null;this.source(job.win,{action:'cancel-prepare',requestKey:job.requestKey}).catch(()=>{});
  }
 }
 prime(win,p){
  if(!['songs','library-songs'].includes(p.kind)||!/^\w[\w.-]{0,199}$/.test(String(p.id)))throw Error('INVALID_ARGUMENTS');
  if(!this.enabled||!this.session?.active.quality||this.session.manual||this.session.standby&&!this.session.standby.ready)return Promise.resolve({ready:false});
  if(this.primeJob?.id===p.id&&this.primeJob.kind===p.kind)return this.primeJob.promise;
  this.cancelPrime();
  const job={win,id:p.id,kind:p.kind,requestKey:'native-'+(++this.generation)};this.primeJob=job;
  // Manifests only: no extra decoder, licensed host, audio download or output.
  job.promise=this.source(win,{action:'prime',id:p.id,kind:p.kind,requestKey:job.requestKey,allowStereo:true,fairplay:!!this.session.nativeRuntime?.fairplay})
   .finally(()=>{if(this.primeJob===job)this.primeJob=null;});
  return job.promise;
 }
 primeList(win,result){
  if(this.primeJob||this.session?.manual)return;
  clearTimeout(this.primeTimer);
  const items=(result?.items||result?.tracks||[]).filter(p=>['songs','library-songs'].includes(p.kind)&&/^\w[\w.-]{0,199}$/.test(String(p.id))).slice(0,2),revision=this.revision;
  const next=()=>{if(this.revision!==revision||!items.length)return;
   this.prime(win,items.shift()).catch(()=>{}).finally(()=>{if(this.revision===revision&&items.length)this.primeTimer=setTimeout(next,150);});};
  if(items.length)this.primeTimer=setTimeout(next,200);
 }
 pipePcm(r,deck,child){
  const source=child.stdio[3],input=r.mixer.stdio[3+deck.slot];let buffer=Buffer.alloc(0),waiting=false,closed=false;
  const drain=()=>{waiting=false;flush();if(!waiting&&!closed)source.resume();};
  const flush=()=>{
   while(!closed&&!waiting&&buffer.length>=8){
    const generation=buffer.readUInt32LE(0),length=buffer.readUInt32LE(4);
    if(!generation||length<8||length>1048576||length%8){this.deckFailed(r,deck,'SPATIAL_PCM_FORMAT');return;}
    if(buffer.length<length+8)return;
    const frame=buffer.subarray(0,length+8);buffer=buffer.subarray(length+8);
    if(generation!==deck.generation)continue;
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
  this.applyHeadphones(r);
  this.send(mixer,{type:'pause',paused:r.paused});
  const metadata=r.active.metadata,id=/^\d{1,20}$/.test(String(metadata.catalogId||''))?metadata.catalogId:metadata.id;
  await this.loadDeck(r,r.active,await this.source(r.win,{action:'prepare',requestKey:r.active.requestKey,id,kind:String(id).startsWith('i.')?'library-songs':'songs',allowStereo:true,fairplay:!!r.nativeRuntime?.fairplay}),r.state.position);
 }
 async loadDeck(r,deck,prepared,position=0){
  deck.scene=this.scenes.render();
  deck.context=prepared.contextId;deck.prepared=prepared;
  if(this.session!==r||!r.decks.includes(deck)){this.source(r.win,{action:'close',contextId:deck.context}).catch(()=>{});return;}
  if(deck===r.active&&Number.isFinite(r.pendingSeek)){position=r.pendingSeek;delete r.pendingSeek;}
  if(deck===r.active){
   deck.metadata=prepared.metadata;
   this.page(r.win,{method:'play',params:{kind:String(prepared.metadata.id).startsWith('i.')?'library-songs':'songs',id:prepared.metadata.id,native:true,metadata:prepared.metadata}}).catch(()=>{});
  }
  this.send(r.mixer,{type:'slot',slot:deck.slot,generation:deck.generation,position,preroll:deck.manual?.16:2});
  // Download encrypted first-segment bytes while the licensed host starts or
  // authorizes the track. The source keeps them private in its bounded cache.
  this.source(r.win,{action:'prefetch',contextId:deck.context,index:Math.max(0,prepared.segments?.findIndex(s=>s.start+s.duration>position)||0)}).catch(()=>{});
  const reusable=deck.child&&!deck.child.killed&&deck.child.exitCode==null&&deck.persistent&&prepared.drm==='fairplay'&&deck.loads<8&&(deck.used||0)+prepared.licences.length<=16;
  deck.reusedHost=!!reusable;
  if(reusable){
   deck.loads++;this.send(deck.child,{type:'load',prepared,position,generation:deck.generation,scene:deck.scene,fullPreroll:r.nativeOnly===true});return;
  }
  this.destroyWorker(deck);deck.persistent=prepared.drm==='fairplay';deck.loads=1;deck.used=0;
  const child=deck.child=this.spawn(process.env.EMBERBOX_SPATIAL_WORKER,['pipe','pipe','pipe','pipe'],r.rate);
  this.wire(child,v=>{if(deck.child===child)this.message(r,deck,v);},code=>{if(deck.child===child)this.deckFailed(r,deck,code);});
  this.pipePcm(r,deck,child);
  this.send(child,{type:'start',runtime:r.nativeRuntime,outputRate:r.rate,cdm:process.env.EMBERBOX_WIDEVINE,prepared,position,pcm:true,generation:deck.generation,scene:deck.scene,fullPreroll:r.nativeOnly===true});
 }
 message(r,deck,value){
  if(this.session!==r)return;
  if(value.type==='host-ready'){
   deck.hostReady=true;
   if(deck===r.active)this.warm(r,1-deck.slot);
   return;
  }
  if(value.type==='host-capacity'){if(Number.isInteger(value.used)&&value.used>=0&&value.used<=16)deck.used=value.used;return;}
  if(!r.decks.includes(deck))return;
  if(value.generation!==undefined&&value.generation!==deck.generation)return;
  if(value.type==='host-exhausted'){
   this.destroyWorker(deck);this.loadDeck(r,deck,deck.prepared,deck.position||0).catch(()=>this.deckFailed(r,deck,'SPATIAL_PLAYBACK_FAILED'));return;
  }
  if(value.type==='request'){
   if(typeof value.id!=='string'||value.id.length>100||!['license','segment'].includes(value.action))return;
   const params=value.action==='license'?{index:value.index,challenge:value.challenge}:{index:value.index,offset:value.offset};
   if(value.contextId&&value.contextId!==deck.context){this.send(deck.child,{type:'response',id:value.id,error:'SPATIAL_STALE_CONTEXT'});return;}
   this.source(r.win,{action:value.action,contextId:value.contextId||deck.context,...params}).then(result=>{
    if(this.session===r&&r.decks.includes(deck)){
     if(value.action==='segment'&&deck===r.active)this.fragmentDebug={index:value.index,total:result.total,initBytes:result.initBytes,originalOffset:result.originalOffset};
     this.send(deck.child,{type:'response',id:value.id,result});}
   }).catch(e=>{
    if(Number.isInteger(e.appleStatus))this.fragmentDebug={...this.fragmentDebug,licenseStatus:e.appleStatus};
    this.send(deck.child,{type:'response',id:value.id,error:errors.has(e.message)?e.message:'SPATIAL_SOURCE_UNSUPPORTED'});
   });
  }else if(value.type==='seek-state'){
   if(['requested','decoding','codec-ready'].includes(value.stage))deck.seekStage=value.stage;
  }else if(value.type==='timing'){
   if(['licenseMs','fragmentMs','pcmMs'].includes(value.stage)&&Number.isInteger(value.ms)&&value.ms>=0&&value.ms<120000){
    deck.timing||={};deck.timing[value.stage]=value.ms;
   }
  }else if(value.type==='quality'){
   const q=value.audioQuality;
   const required=r.requiredQuality;
   if(required&&(q?.codec!==required.codec||q?.variant!==required.variant||Number(q?.sampleRate)<required.sampleRate||required.bitDepth&&Number(q?.bitDepth)<required.bitDepth)){
    this.deckFailed(r,deck,'SPATIAL_QUALITY_CHANGED');return;
   }
   if(q?.codec==='eac3'&&q.variant==='dolby-atmos'&&q.evidence==='decoder'&&['openjoc-binaural','openjoc-speakers'].includes(q.renderer)&&q.sampleRate===48000&&q.channels===2&&(q.outputSampleRate===undefined||q.outputSampleRate===r.rate)){
    if(q.renderer==='openjoc-speakers'&&![20,30,40].includes(q.speakerAngle))return;
    deck.quality={codec:'eac3',variant:'dolby-atmos',evidence:'decoder',renderer:q.renderer,sampleRate:48000,channels:2,
     ...(q.renderer==='openjoc-speakers'?{speakerAngle:q.speakerAngle}:{hrtfPreset:q.hrtfPreset===1?1:0}),...(r.rate!==48000?{outputSampleRate:r.rate}:{})};
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
  if(value.type==='headphones'){
   r.headphoneStatus={active:value.active===true,headroomDb:Number.isFinite(value.headroomDb)?value.headroomDb:0,
    error:value.error==='SCIPY_REQUIRED'?value.error:'',bypass:value.bypass===true};return;
  }
  const deck=r.decks[value.slot];
  if(value.type==='ready'&&deck?.generation===value.generation){deck.ready=true;deck.readyAt=Date.now();}
  else if(value.type==='state'&&deck===r.active&&(value.generation===undefined?!r.seeking:value.generation===deck.generation)){
   if(Array.isArray(value.buffers))this.mixDebug={buffers:value.buffers.slice(0,2).map(row=>Array.isArray(row)?row.slice(0,4).map(v=>Number.isSafeInteger(v)?v:0):[]),frame:Number.isSafeInteger(value.mixFrame)?value.mixFrame:0,played:Number.isSafeInteger(value.playedFrame)?value.playedFrame:0,paused:value.paused===true,fade:Array.isArray(value.fade)?value.fade.slice(0,2).map(v=>Number.isSafeInteger(v)?v:0):[]};
   if(Number.isFinite(value.position)&&value.position>=0&&value.position<=Number(deck.metadata.duration||0)+1){
    if(value.position>r.state.position+.05)r.lastAdvance=Date.now();r.state.position=value.position;}
   if(['preparing','playing','ended'].includes(value.phase))r.state.phase=value.phase;
   r.state.playing=value.playing===true;
   if(r.seeking&&value.seeking===false){r.seeking=false;clearTimeout(r.seekTimer);}
   if(r.nativeOnly&&value.phase==='playing'&&!value.seeking){r.nativeOnly=false;r.requiredQuality=null;}
  }else if(value.type==='flow-started'&&deck&&deck===r.standby&&r.transition?.key===value.key){
   this.blocked.add(String(deck.metadata.id));if(this.blocked.size>32)this.blocked.delete(this.blocked.values().next().value);
   r.active=deck;r.standby=null;r.synchronizing=true;r.state={phase:'playing',position:deck.position||0,playing:!r.paused};r.lastAdvance=Date.now();
   const pending=r.transition;r.transition=null;clearTimeout(pending?.timer);
   if(pending?.manual)this.switchTiming={...deck.timing,reusedDeck:pending.manual.reusedDeck===true,reusedHost:deck.reusedHost===true,
    readyMs:Math.max(0,(deck.readyAt||Date.now())-pending.manual.started),audibleMs:Date.now()-pending.manual.started};
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
  if(this.session!==r)return;
  if(r.idle[deck.slot]===deck){r.idle[deck.slot]=null;this.destroyWorker(deck);return;}
  if(!r.decks.includes(deck))return;
  if(deck===r.active||r.transition){this.failed(r,code);return;}
  if(deck.reusedHost&&!deck.retried&&deck.prepared&&['SPATIAL_LICENSE_REJECTED','SPATIAL_FAIRPLAY_SIGN_IN_REQUIRED'].includes(code)){
   deck.retried=true;deck.ready=false;deck.quality=null;this.destroyWorker(deck);
   this.loadDeck(r,deck,deck.prepared,deck.position||0).catch(()=>this.deckFailed(r,deck,'SPATIAL_PLAYBACK_FAILED'));return;
  }
  deck.error=code;this.flowError=code;this.dropDeck(r,deck);this.send(r.mixer,{type:'cancel'});
 }
 destroyWorker(deck){
  deck.closePcm?.();
  if(deck.child){deck.child.stdio[3]?.unpipe();this.send(deck.child,{type:'stop'});deck.child.kill('SIGTERM');}
  deck.closePcm=null;deck.hostReady=false;
 }
 warm(r,slot){
  if(this.session!==r||!r.nativeRuntime?.fairplay||r.decks[slot]||r.idle[slot])return;
  const deck={slot,generation:0,metadata:{},persistent:true,loads:0,used:0};r.idle[slot]=deck;
  const child=deck.child=this.spawn(process.env.EMBERBOX_SPATIAL_WORKER,['pipe','pipe','pipe','pipe'],r.rate);
  this.wire(child,v=>{if(deck.child===child)this.message(r,deck,v);},code=>{if(deck.child===child)this.deckFailed(r,deck,code);});this.pipePcm(r,deck,child);
  this.send(child,{type:'warm',backend:'fairplay',runtime:r.nativeRuntime,outputRate:r.rate,cdm:process.env.EMBERBOX_WIDEVINE});
 }
 dropDeck(r,deck){
  if(deck.requestKey)this.source(r.win,{action:'cancel-prepare',requestKey:deck.requestKey}).catch(()=>{});
  if(deck.context)this.source(r.win,{action:'close',contextId:deck.context}).catch(()=>{});
  if(r.standby===deck)r.standby=null;if(r.decks[deck.slot]===deck)r.decks[deck.slot]=null;
  const park=this.session===r&&deck.persistent&&!deck.error&&deck.child&&!deck.child.killed&&deck.loads<8&&(deck.used||0)<=12;
  if(park){
   this.send(deck.child,{type:'park'});deck.context=null;deck.prepared=null;deck.generation=0;r.idle[deck.slot]=deck;
  }else{
   this.destroyWorker(deck);
   if(this.session===r&&r.active.persistent)this.warm(r,deck.slot);
  }
 }
 async prepareDeck(r,p,position=0,manual=false){
  const revision=r.flowRevision;
  const slot=1-r.active.slot,deck=r.idle[slot]||{};r.idle[slot]=null;
  Object.assign(deck,{metadata:{id:p.id},kind:p.kind,requestedId:p.id,key:p.key,position,manual,
   slot,generation:++this.generation,quality:null,ready:false,readyAt:0,timing:{},error:null,retried:false,requestKey:'native-'+(++this.generation)});
  r.standby=deck;
  // Descriptor requests can supersede a slow catalogue read. Cancellation
  // keys keep obsolete results from allocating a third source/decoder slot.
  const prepare=async()=>{
   if(this.session!==r||revision!==r.flowRevision||r.standby!==deck)throw Error('FLOW_CANCELLED');
   const freeUntil=Date.now()+2000;
   while(r.decks[deck.slot]&&Date.now()<freeUntil)await new Promise(resolve=>setTimeout(resolve,20));
   if(this.session!==r||revision!==r.flowRevision||r.standby!==deck)throw Error('FLOW_CANCELLED');
   if(r.decks[deck.slot])throw Error('FLOW_NOT_READY');
   r.decks[deck.slot]=deck;
   const started=Date.now();
   const prime=this.primeJob;
   if(prime?.id===p.id&&prime.kind===p.kind)await prime.promise.catch(()=>{});
   if(this.session!==r||revision!==r.flowRevision||r.standby!==deck)throw Error('FLOW_CANCELLED');
   const prepared=await this.source(r.win,{action:'prepare',requestKey:deck.requestKey,id:p.id,kind:p.kind,allowStereo:true,fairplay:!!r.nativeRuntime?.fairplay});
   deck.timing.sourceMs=Date.now()-started;
   if(this.session!==r||revision!==r.flowRevision||r.standby!==deck){
    await this.source(r.win,{action:'close',contextId:prepared.contextId}).catch(()=>{});throw Error('FLOW_CANCELLED');}
   deck.metadata=prepared.metadata;
   await this.loadDeck(r,deck,prepared,position);
   return deck;
  };
  deck.loading=prepare().catch(error=>{
   if(revision===r.flowRevision&&r.standby===deck)this.dropDeck(r,deck);
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
  this.cancelPrime(p);
  r.seeking=false;r.nativeOnly=false;r.requiredQuality=null;clearTimeout(r.seekTimer);
  const request={id:p.id,kind:p.kind,position,started:Date.now()};r.manual=request;this.error='';this.switchError=null;
  // Finish a cancelled overlap before reusing its slot. A new Play command
  // may arrive while that output clock is paused.
  if(r.paused&&r.decks.filter(Boolean).length>1){r.paused=false;this.send(r.mixer,{type:'pause',paused:false});}
  const reusable=r.standby&&!r.transition&&position===0&&
   (r.standby.requestedId===p.id||this.matches(r.standby.metadata,{id:p.id,catalogId:p.id}))?r.standby:null;
  request.reusedDeck=!!reusable;
  r.manualTask=(async()=>{
   let deck=reusable;
   if(!deck){
    await this.flow(r,{operation:'cancel',force:true});
    if(r.manual!==request||this.session!==r)return;
    deck=await this.prepareDeck(r,{...p,key:'manual-'+(++this.generation)},position,true);
   }else if(deck.loading)await deck.loading;
   const valid=()=>r.manual===request;
   this.send(r.mixer,{type:'preroll',slot:deck.slot,generation:deck.generation,seconds:.16});
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
 seek(r,position){
  const deck=r.active;
  r.manual=null;r.flowRevision++;clearTimeout(r.transition?.timer);r.transition?.reject(Error('FLOW_CANCELLED'));r.transition=null;
  for(const other of [...r.decks])if(other&&other!==deck)this.dropDeck(r,other);
  // A superseded source negotiation may not yet own a slot.
  if(r.standby&&r.standby!==deck)this.dropDeck(r,r.standby);
  r.standby=null;r.seeking=true;this.switchError=null;this.error='';r.lastAdvance=Date.now();
  r.state={phase:'preparing',position,playing:!r.paused};
  if(!deck.child){r.pendingSeek=position;return {ok:true,seeking:true,position};}
  deck.generation=++this.generation;deck.ready=false;deck.position=position;
  this.send(r.mixer,{type:'seek',slot:deck.slot,generation:deck.generation,position});
  deck.scene=this.scenes.render();r.scenePending=false;
  this.send(deck.child,{type:'seek',generation:deck.generation,position,scene:deck.scene});
  clearTimeout(r.seekTimer);r.seekTimer=setTimeout(()=>{
   if(this.session===r&&r.seeking)this.failed(r,'SPATIAL_SEEK_TIMEOUT');
  },12000);
  return {ok:true,seeking:true,position};
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
   if(!r.mixer||!r.active.quality||r.manual||r.seeking||r.paused||r.state.phase!=='playing')throw Error('FLOW_NOT_READY');
   if(!['songs','library-songs'].includes(p.kind)||!/^\w[\w.-]{0,199}$/.test(String(p.id))||typeof p.key!=='string'||p.key.length>80)throw Error('INVALID_ARGUMENTS');
   await this.flow(r,{operation:'cancel'});const revision=r.flowRevision;
   let deck;
   try{
    deck=await this.prepareDeck(r,p);
    await this.waitReady(r,deck,()=>revision===r.flowRevision);return {ready:true};
   }catch(e){if(revision===r.flowRevision&&deck&&r.standby===deck)this.dropDeck(r,deck);throw e;}
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
 async failed(r,code){
  if(this.session!==r)return;this.error=code;
  // A failed warm seek gets one native retry at the chosen position. Never
  // hide it by playing the browser's lower-quality AAC version instead.
  if(r.seeking&&r.active.quality&&!r.nativeOnly){
   const metadata=r.active.metadata,position=r.state.position,paused=r.paused,required=r.active.quality;
   const stopping=this.stop(false),revision=this.revision;await stopping;
   if(this.session||this.revision!==revision)return;
   this.begin(r.win,metadata,position,paused);this.session.nativeOnly=true;this.session.requiredQuality=required;return;
  }
  await this.stop(!r.nativeOnly).catch(()=>{});
 }
 async restore(r,revision){
  if(r.win.isDestroyed())return;const deck=r.active,current=await this.page(r.win,{method:'status',params:{}});
  if(revision!==this.revision||this.session||current.playing&&!r.synchronizing&&!this.matches(deck.metadata,current))return;
  const id=/^\d{1,20}$/.test(String(deck.metadata.catalogId||''))?deck.metadata.catalogId:deck.metadata.id;
  await this.page(r.win,{method:'play',params:{kind:String(id).startsWith('i.')?'library-songs':'songs',id,
   position:r.state.position,paused:r.paused||r.state.phase==='ended'}});
 }
 async stop(restore=false){
  this.cancelPrime();
  const r=this.session;if(!r)return;this.session=null;const revision=++this.revision;
  clearTimeout(r.watchdog);clearTimeout(r.seekTimer);clearInterval(r.stall);r.flowRevision++;
  clearTimeout(r.transition?.timer);r.transition?.reject(Error('FLOW_CANCELLED'));r.transition=null;
  for(const deck of [...r.decks])if(deck)this.dropDeck(r,deck);
  for(const deck of r.idle)if(deck)this.destroyWorker(deck);r.idle=[null,null];
  if(r.mixer){this.send(r.mixer,{type:'stop'});r.mixer.kill('SIGTERM');}
  if(restore)await this.restore(r,revision);
 }
 async intercept(win,request){
  if(request.method==='spatial'&&['scene','output'].includes(request.params?.operation)){
   if(request.params.operation==='scene')this.scenes.set(request.params);
   else this.scenes.setOutput(request.params);
   this.applyScene();return this.info();
  }
  if(request.method==='spatial'&&request.params?.operation==='formats')return this.source(win,{action:'inspect',id:request.params.id,kind:request.params.kind,enhanced:request.params.enhanced,extended:request.params.extended,encryption:request.params.encryption,fairplayMetadata:request.params.fairplayMetadata});
  if(request.method==='spatial'&&request.params?.operation==='prime')return this.prime(win,request.params);
  if(['play','transport','seek','enable','spatial'].includes(request.method))this.revision++;
  if(request.method==='spatial')return this.configure(request.params?.enabled);
  const r=this.session,p=request.params||{};
  if((!r||!r.mixer||!r.active.quality)&&this.enabled&&runtime()&&request.method==='play'&&['songs','library-songs'].includes(p.kind)&&/^\w[\w.-]{0,199}$/.test(String(p.id))&&p.paused!==true){
   // Start the chosen native asset directly. Warming a second browser AAC
   // queue first adds a network/DRM startup and can stall setQueue/play.
   // A second click during cold preparation must supersede that selection,
   // too, rather than falling through into MusicKit's other audio pipeline.
   let revision=this.revision;
   if(r){const stopping=this.stop(false);revision=this.revision;await stopping;}
   if(revision!==this.revision)return {ok:true,superseded:true};
   await this.page(win,{method:'transport',params:{action:'pause'}});
   if(revision!==this.revision)return {ok:true,superseded:true};
   if(this.session)return this.select(this.session,{kind:p.kind,id:String(p.id)},Math.max(0,Number(p.position)||0));
   this.begin(win,{id:String(p.id),catalogId:p.kind==='songs'?String(p.id):''},Math.max(0,Number(p.position)||0));
   this.session.nativeOnly=true;
   return {ok:true,preparing:true};
  }
  if(!r)return null;
  if(request.method==='flow')return this.flow(r,request.params||{});
  if(request.method==='seek'){
   const position=Number(request.params?.position);if(!Number.isFinite(position)||position<0)throw Error('INVALID_ARGUMENTS');
   const metadata=r.active.metadata,target=Math.min(position,Number(metadata.duration)||position);
   return this.seek(r,target);
  }
  if(request.method==='play'&&['songs','library-songs'].includes(request.params?.kind)&&/^\w[\w.-]{0,199}$/.test(String(request.params?.id))&&request.params?.paused!==true&&r.mixer&&r.active.quality){
   return this.select(r,{kind:request.params.kind,id:String(request.params.id)},Math.max(0,Number(request.params.position)||0));
  }
  if(request.method==='transport'&&['pause','resume','toggle'].includes(request.params?.action)){
   r.paused=request.params.action==='toggle'?!r.paused:request.params.action==='pause';r.state.playing=!r.paused;r.lastAdvance=Date.now();
   if(r.paused&&r.manual){r.manual=null;await this.flow(r,{operation:'cancel',force:true});}
   this.send(r.mixer,{type:'pause',paused:r.paused});
   if(!r.paused&&r.state.phase==='ended')return this.seek(r,0);
   return {ok:true};
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
