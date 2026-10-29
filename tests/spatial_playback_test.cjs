'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'ember-spatial-controller-'));
const calls=[],commands=[];let defer=null;
fs.writeFileSync(path.join(root,'host'),'fixture');fs.writeFileSync(path.join(root,'decoder'),'fixture');
process.env.EMBERBOX_SPATIAL_RUNTIME=path.join(root,'runtime.json');process.env.EMBERBOX_SPATIAL_CONFIG=path.join(root,'preference.json');
fs.writeFileSync(process.env.EMBERBOX_SPATIAL_RUNTIME,JSON.stringify({schema:1,host:path.join(root,'host'),decoder:path.join(root,'decoder')}));
const {SpatialPlayback}=require('../src/apple_web_host/spatial.cjs');
const win={isDestroyed:()=>false};
const metadata={id:'123',catalogId:'123',position:42,duration:180,authorized:true,playing:true,
 availableFormats:['dolby-atmos'],audioQuality:{codec:'aac',evidence:'decoder'},emberFlow:true,emberBeatSync:true};
const quality={codec:'eac3',variant:'dolby-atmos',evidence:'decoder',renderer:'openjoc-binaural',sampleRate:48000,channels:2};
const next={...metadata,id:'456',catalogId:'456',title:'Next'};
let current={...metadata};
const page=async(w,request)=>{calls.push(request);if(request.method==='status')return defer?await defer:{...current};
 if(request.method==='play')current={...current,id:request.params.id,catalogId:request.params.id};return {ok:true};};
const p=new SpatialPlayback(page,async()=>{});
const realLoadDeck=p.loadDeck.bind(p);
// A killed PCM producer must never leave half a frame in a reusable pipe.
const {PassThrough}=require('node:stream'),{EventEmitter}=require('node:events');
const raw=new EventEmitter(),forwarded=[];raw.write=frame=>{forwarded.push(Buffer.from(frame));return true;};
const pcmSession={mixer:{stdio:[null,null,null,raw]}},partial={slot:0,generation:21},replacement={slot:0,generation:22};
function packet(generation){const frame=Buffer.alloc(24);frame.writeUInt32LE(generation);frame.writeUInt32LE(16,4);return frame;}
const oldPipe=new PassThrough();p.pipePcm(pcmSession,partial,{stdio:[null,null,null,oldPipe]});
oldPipe.write(packet(21).subarray(0,13));partial.closePcm();assert.equal(forwarded.length,0);
const newPipe=new PassThrough();p.pipePcm(pcmSession,replacement,{stdio:[null,null,null,newPipe]});
newPipe.write(packet(22).subarray(0,3));newPipe.write(packet(22).subarray(3));
// A warm seek keeps the producer pipe. Discard its old whole generation.
replacement.generation=24;newPipe.write(Buffer.concat([packet(22),packet(24)]));
assert.deepEqual(forwarded.pop(),packet(24));
assert.equal(forwarded.length,1);assert.deepEqual(forwarded[0],packet(22));replacement.closePcm();
let blocked=true;raw.write=frame=>{forwarded.push(Buffer.from(frame));return !blocked;};
const pressured={slot:0,generation:23},pressuredPipe=new PassThrough();
p.pipePcm(pcmSession,pressured,{stdio:[null,null,null,pressuredPipe]});
pressuredPipe.write(Buffer.concat([packet(23),packet(23)]));assert.equal(forwarded.length,2);
blocked=false;raw.emit('drain');assert.equal(forwarded.length,3);pressured.closePcm();
function child(){return {killed:false,stdin:{writable:true,write:s=>commands.push(JSON.parse(s))},stdio:[null,null,null,{unpipe(){}}],kill(){this.killed=true;}};}
p.load=async r=>{r.mixer=child();r.active.child=child();};
p.source=async(w,request)=>request.action==='prepare'?{contextId:'context-'+request.id,metadata:request.id==='123'?metadata:next}:{};
p.loadDeck=async(r,deck,prepared)=>{deck.context=prepared.contextId;deck.child=child();deck.quality=quality;deck.ready=true;};
(async()=>{
 assert.equal(p.merge(win,metadata).emberFlow,true);
 await p.configure(true);let out=p.merge(win,metadata),r=p.session,d=r.active;
 assert(r);assert.equal(out.emberFlow,false);assert.equal(out.emberBeatSync,false);assert.equal(out.audioQuality.codec,'aac');
 p.message(r,d,{type:'quality',audioQuality:{codec:'aac',variant:'dolby-atmos',evidence:'decoder'}});assert.equal(d.quality,null);
 p.message(r,d,{type:'quality',audioQuality:quality});
 p.mixerMessage(r,{type:'state',slot:0,position:45,phase:'playing',playing:true});out=p.merge(win,metadata);
 assert.equal(out.audioQuality.variant,'dolby-atmos');assert.equal(out.position,45);assert.equal(out.emberFlow,true);
 await p.intercept(win,{method:'transport',params:{action:'pause'}});assert.equal(p.merge(win,metadata).playing,false);
 await p.intercept(win,{method:'transport',params:{action:'resume'}});assert.equal(commands.at(-1).paused,false);
 await p.intercept(win,{method:'transport',params:{action:'pause'}});
 const decoder=d.child,sourceContext=d.context,output=r.mixer;
 await p.intercept(win,{method:'seek',params:{position:90}});
 assert.equal(d.child,decoder);assert.equal(decoder.killed,false);assert.equal(d.context,sourceContext);assert.equal(r.mixer,output);assert.equal(p.session,r);
 assert.equal(r.state.position,90);assert.equal(r.paused,true);assert.equal(commands.at(-1).type,'seek');
 const staleGeneration=d.generation;await p.intercept(win,{method:'seek',params:{position:12}});
 p.mixerMessage(r,{type:'state',slot:0,generation:staleGeneration,position:91,phase:'playing',playing:true,seeking:false});
 assert.equal(r.state.position,12);assert.equal(r.seeking,true);assert.equal(r.paused,true);
 p.mixerMessage(r,{type:'state',slot:0,generation:d.generation,position:12,phase:'playing',playing:false,seeking:false});
 assert.equal(r.seeking,false);assert.equal(p.merge(win,metadata).playing,false);
 await p.intercept(win,{method:'seek',params:{position:90}});
 const playsBeforeSeekFailure=calls.filter(c=>c.method==='play').length;
 await p.failed(r,'SPATIAL_SEEK_TIMEOUT');assert(p.session);assert.equal(p.session.nativeOnly,true);assert.equal(p.session.state.position,90);
 assert.equal(calls.filter(c=>c.method==='play').length,playsBeforeSeekFailure,'A seek failure silently downgraded to web AAC');
 r=p.session;p.message(r,r.active,{type:'quality',audioQuality:{codec:'aac',evidence:'decoder',sampleRate:48000,channels:2,outputSampleRate:48000}});
 assert.equal(p.session,null,'A native seek recovery admitted a lower-quality rendition');
 assert.equal(calls.filter(c=>c.method==='play').length,playsBeforeSeekFailure);
 assert.equal(p.merge(win,metadata).audioQuality.codec,'aac');assert.equal(p.session,null);
 await p.configure(false);assert.equal(JSON.parse(fs.readFileSync(process.env.EMBERBOX_SPATIAL_CONFIG)).enabled,false);
 await p.configure(true);p.merge(win,metadata);r=p.session;
 let release;defer=new Promise(resolve=>release=resolve);
 const restore=p.failed(r,'SPATIAL_NETWORK');
 await p.intercept(win,{method:'play',params:{id:'456'}});const before=calls.filter(c=>c.method==='play').length;
 release({...metadata});await restore;defer=null;
 assert.equal(calls.filter(c=>c.method==='play').length,before,'Late fallback replayed the previous song');
 await p.configure(true);p.merge(win,metadata);r=p.session;r.state.position=174;r.state.phase='playing';r.active.quality=quality;
 assert.deepEqual(await p.flow(r,{operation:'prepare',key:'entry',kind:'songs',id:'456'}),{ready:true});
 const standby=r.standby,old=r.active;
 const transition=p.flow(r,{operation:'transition',key:'entry',duration:6});
 assert.equal(commands.at(-1).type,'transition');assert.equal(r.active,old,'Promoted before audible output');
 p.mixerMessage(r,{type:'flow-started',key:'entry',slot:1,duration:6});
 assert.equal((await transition).overlap,true);assert.equal(r.active,standby);
 out=p.merge(win,next);assert.equal(out.id,'456');assert.equal(out.audioQuality.variant,'dolby-atmos');
 p.mixerMessage(r,{type:'released',slot:0,generation:old.generation});assert(old.child.killed);assert.equal(r.decks[0],null);
 p.mixerMessage(r,{type:'state',slot:1,position:180,phase:'ended',playing:false});assert.equal(p.merge(win,next).ended,true);
 await p.stop(false);current={...metadata};await p.configure(true);p.merge(win,metadata);r=p.session;r.state.position=174;r.state.phase='playing';r.active.quality=quality;
 await p.flow(r,{operation:'prepare',key:'cancel',kind:'songs',id:'456'});
 const cancelled=p.flow(r,{operation:'transition',key:'cancel',duration:6});
 const rejection=assert.rejects(cancelled,/FLOW_CANCELLED/);await p.flow(r,{operation:'cancel'});await rejection;
 assert.equal(commands.at(-1).keep,0);assert.equal(r.active.metadata.id,'123');
 p.mixerMessage(r,{type:'released',slot:1,generation:r.decks[1].generation});
 // Manual Next consumes the actual prepared deck and keeps the output clock.
 await p.flow(r,{operation:'prepare',key:'manual-ready',kind:'songs',id:'456'});
 const primed=r.standby,mixer=r.mixer,outgoing=r.active;
 await p.flow(r,{operation:'cancel',preserve:true});assert.equal(r.standby,primed);
 const tick=async()=>await new Promise(resolve=>setImmediate(resolve));
 const chosen=await p.intercept(win,{method:'play',params:{kind:'songs',id:'456'}});
 await tick();assert.equal(chosen.preparing,false);assert.equal(p.session,r);assert.equal(r.mixer,mixer);
 assert.equal(r.standby,primed);assert.equal(outgoing.child.killed,false);
 assert.equal(commands.at(-1).duration,.22);assert.equal(commands.at(-1).manual,true);
 p.mixerMessage(r,{type:'flow-started',key:primed.key,slot:primed.slot,duration:.22});
 await r.manualTask;assert.equal(r.active,primed);assert.equal(r.manual,null);
 assert.equal(calls.at(-1).params.native,true,'Native handover must not warm MusicKit AAC again');
 p.mixerMessage(r,{type:'released',slot:outgoing.slot,generation:outgoing.generation});
 // A second click cancels stale source preparation before it can spawn/play.
 const source=p.source;let releaseSource,entered=false;
 p.source=async(w,request)=>{
  if(request.action==='prepare'&&request.id==='123'&&!entered){entered=true;await new Promise(resolve=>releaseSource=resolve);}
  return source(w,request);
 };
 await p.intercept(win,{method:'play',params:{kind:'songs',id:'123'}});await tick();assert(entered);
 await p.intercept(win,{method:'play',params:{kind:'songs',id:'456'}});await tick();await tick();
 assert.equal(r.standby.requestedId,'456','Latest selection waited for obsolete catalogue preparation');
 assert.equal(commands.at(-1).type,'transition','Latest selected track was not ready before the old API returned');
 releaseSource();await tick();await tick();
 assert.equal(r.active,primed,'An obsolete click must never replace audible metadata');
 assert.equal(r.standby.requestedId,'456');assert.equal(r.decks.filter(Boolean).length,2);
 const latest=r.standby;
 p.mixerMessage(r,{type:'flow-started',key:latest.key,slot:latest.slot,duration:.22});
 await r.manualTask;assert.equal(r.active,latest);p.source=source;
 p.mixerMessage(r,{type:'released',slot:primed.slot,generation:primed.generation});
 // Rewind keeps both the native output and same licensed worker alive.
 const warmWorker=r.active.child,warmContext=r.active.context;
 await p.intercept(win,{method:'seek',params:{position:0}});await tick();
 assert.equal(p.session,r);assert.equal(r.mixer,mixer);assert.equal(r.manual,null);assert(r.seeking);
 assert.equal(r.active.child,warmWorker);assert.equal(r.active.context,warmContext);
 await p.intercept(win,{method:'transport',params:{action:'pause'}});
 assert.equal(r.manual,null);assert.equal(r.paused,true);assert.equal(r.active,latest);
 p.mixerMessage(r,{type:'state',slot:latest.slot,generation:latest.generation,position:0,phase:'playing',playing:false,seeking:false});
 assert.equal(r.seeking,false);
 const goodSource=p.source;p.source=async()=>{throw Error('SPATIAL_NETWORK');};
 await p.intercept(win,{method:'play',params:{kind:'songs',id:'123'}});await r.manualTask;
 assert.equal(r.active,latest);assert.equal(latest.child.killed,false);
 assert.equal(p.info().switchError.id,'123');assert.equal(p.info().error,'');
 assert.equal(r.decks.filter(Boolean).length,1);p.source=goodSource;
 await assert.rejects(p.intercept(win,{method:'spatial',params:{enabled:'true'}}),/INVALID_ARGUMENTS/);
 await p.stop(false);
 await p.configure(true);current={...metadata};p.merge(win,metadata);r=p.session;r.active.quality=quality;r.state.phase='playing';const hoverOutgoing=r.active;
 // Hover preparation is coalesced, and clicking that same song joins its
 // descriptor negotiation rather than cancelling/repeating the network work.
 const ordinarySource=p.source;let primeRelease,primeCalls=0;
 p.source=async(w,request)=>{
  if(request.action==='prime'){primeCalls++;await new Promise(resolve=>primeRelease=resolve);return {ready:true};}
  return ordinarySource(w,request);
 };
 const hover=p.prime(win,{kind:'songs',id:'123'});
 const sameHover=p.prime(win,{kind:'songs',id:'123'});assert.equal(hover,sameHover);assert.equal(primeCalls,1);
 await p.intercept(win,{method:'play',params:{kind:'songs',id:'123'}});await tick();
 assert.equal(r.standby.metadata.id,'123');assert.equal(r.standby.ready,false);
 primeRelease();await hover;await tick();await tick();
 const hovered=r.standby;
 assert.equal(commands.at(-1).type,'transition');
 p.mixerMessage(r,{type:'flow-started',key:hovered.key,slot:hovered.slot,duration:.22});await r.manualTask;
 p.mixerMessage(r,{type:'released',slot:hoverOutgoing.slot,generation:hoverOutgoing.generation});
 p.source=ordinarySource;
 await p.stop(false);
 const playCount=calls.filter(c=>c.method==='play'&&c.params.native!==true).length;
 const coldNative=await p.intercept(win,{method:'play',params:{kind:'songs',id:'456',position:10}});
 assert.equal(coldNative.preparing,true);assert.equal(p.session.active.metadata.id,'456');
 assert.equal(p.session.state.position,10);assert.equal(p.session.nativeOnly,true);
 const pendingCold=p.session;
 await p.intercept(win,{method:'play',params:{kind:'songs',id:'123'}});
 assert.notEqual(p.session,pendingCold);assert.equal(p.session.active.metadata.id,'123');
 assert.equal(calls.filter(c=>c.method==='play'&&c.params.native!==true).length,playCount,'Native startup warmed an unnecessary browser AAC queue');
 await p.stop(false);
 const realPage=p.page;let pauseRelease,firstPause=true;
 p.page=async(w,request)=>{
  if(firstPause&&request.method==='transport'){firstPause=false;await new Promise(resolve=>pauseRelease=resolve);}
  return realPage(w,request);
 };
 const lateCold=p.intercept(win,{method:'play',params:{kind:'songs',id:'123'}});await tick();
 await p.intercept(win,{method:'play',params:{kind:'songs',id:'456'}});
 pauseRelease();assert.equal((await lateCold).superseded,true);
 assert.equal(p.session.active.metadata.id,'456','An older pause acknowledgement replaced the latest cold selection');
 p.page=realPage;await p.stop(false);
 const profile=path.join(root,'native-profile');fs.mkdirSync(profile);fs.writeFileSync(path.join(profile,'session-ready'),'fixture');
 process.env.EMBERBOX_FAIRPLAY_RUNTIME=path.join(root,'fairplay.json');
 fs.writeFileSync(process.env.EMBERBOX_FAIRPLAY_RUNTIME,JSON.stringify({schema:1,library:path.join(root,'host'),librarySha256:'a'.repeat(64),profile}));
 const ordinary={...metadata,id:'789',catalogId:'789',availableFormats:['lossless']};
 await p.configure(true);p.merge(win,ordinary);r=p.session;assert(r,'Signed-in native Lossless should also start for ordinary tracks');
 assert.equal(r.rate,192000);
 const alac={codec:'alac',evidence:'decoder',sampleRate:96000,bitDepth:24,channels:2,outputSampleRate:192000};
 p.message(r,r.active,{type:'quality',audioQuality:{...alac,evidence:'catalog'}});assert.equal(r.active.quality,null);
 p.message(r,r.active,{type:'quality',audioQuality:{...alac,outputSampleRate:48000}});assert.equal(r.active.quality,null);
 p.message(r,r.active,{type:'quality',audioQuality:alac});assert.deepEqual(r.active.quality,alac);
 // A warm host with an expired opaque lease gets one fresh-host retry,
 // without replacing the audible track or negotiating a different asset.
 const refresh={slot:1,generation:89,metadata:next,child:child(),persistent:true,loads:2,used:3,reusedHost:true,prepared:{contextId:'retry-context',metadata:next},position:0};
 r.decks[1]=refresh;r.standby=refresh;const expired=refresh.child,loader=p.loadDeck,playingQuality=r.active.quality;let retries=0;
 p.loadDeck=async(...args)=>{retries++;return loader(...args);};
 p.deckFailed(r,refresh,'SPATIAL_LICENSE_REJECTED');assert.equal(retries,1);assert.equal(expired.killed,true);assert.equal(r.standby,refresh);assert.equal(r.active.quality,playingQuality);
 p.deckFailed(r,refresh,'SPATIAL_LICENSE_REJECTED');assert.equal(retries,1);assert.equal(r.standby,null);assert.equal(p.info().error,'');p.loadDeck=loader;
 // Reuse a parked licensed host without a new native process or login.
 const parked={slot:1,generation:90,metadata:next,child:child(),persistent:true,loads:2,used:3};
 const kept=parked.child;r.decks[1]=parked;r.standby=parked;
 const descriptor={contextId:'new-track-context',metadata:next,drm:'fairplay',licences:[{uri:'fixture'}],segments:[{start:0,duration:10}]};
 await realLoadDeck(r,parked,descriptor,0);
 assert.equal(parked.child,kept);assert.equal(parked.loads,3);assert.equal(commands.at(-1).type,'load');
 let sourceReads=0;const oldSource=p.source;p.source=async()=>{sourceReads++;return {};};
 p.message(r,parked,{type:'request',id:'late-segment',action:'segment',contextId:'old-track-context',index:0,offset:0});
 assert.equal(sourceReads,0);assert.equal(commands.at(-1).error,'SPATIAL_STALE_CONTEXT');
 p.source=oldSource;p.dropDeck(r,parked);assert.equal(kept.killed,false);assert.equal(r.idle[1],parked);assert.equal(parked.generation,0);
 parked.loads=8;r.idle[1]=null;r.decks[1]=parked;p.dropDeck(r,parked);
 assert.equal(kept.killed,true,'An exhausted host was retained without a capacity bound');
 await p.stop(false);
 console.log('PASS spatial lifecycle and native Flow: quality evidence, output-clock promotion, release, cancellation, pause, seek, fallback and stale recovery');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>{p.stop(false);fs.rmSync(root,{recursive:true,force:true});});
