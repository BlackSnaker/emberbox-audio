'use strict';
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const host='https://audio-ssl.itunes.apple.com',requests=[];
const key=n=>Buffer.from(Uint8Array.from({length:16},(_,i)=>i+n)).toString('base64');
let noAtmos=false;
const files={
 '/master':()=>`#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=768000,CODECS="${noAtmos?'mp4a.40.2':'ec-3'}"\neac3.m3u8?session=NEVER_EXPORT\n`,
 '/extended':()=>`#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1800000,CODECS="alac"\nlossless.m3u8?session=NEVER_EXPORT\n`,
 '/lossless.m3u8':()=>`#EXTM3U\n#EXT-X-KEY:METHOD=SAMPLE-AES,KEYFORMAT="com.apple.streamingkeydelivery",URI="skd://NEVER_EXPORT"\n#EXTINF:10,\nprivate-audio.mp4\n`,
 '/eac3.m3u8':()=>`#EXTM3U\n#EXT-X-KEY:METHOD=SAMPLE-AES,KEYFORMAT="com.widevine",URI="data:;base64,${key(0)}"\n#EXT-X-MAP:URI="audio.mp4",BYTERANGE="100@0"\n#EXT-X-KEY:METHOD=SAMPLE-AES,KEYFORMAT="com.widevine",URI="data:;base64,${key(1)}"\n#EXTINF:10,\n#EXT-X-BYTERANGE:20@100\naudio.mp4\n#EXT-X-ENDLIST\n`,
 '/certificate':()=>new Uint8Array([1,2,3]),'/audio.mp4':()=>Uint8Array.from({length:120},(_,i)=>i)
};
const music={isAuthorized:true,storefrontId:'us',api:{music:async(url)=>{assert.equal(url,'/v1/catalog/us/songs/789');return {data:{data:[{id:'789',attributes:{name:'Next song',artistName:'Example',durationInMillis:180000,playParams:{id:'789',kind:'song'},extendedAssetUrls:{enhancedHls:host+'/extended?session=NEVER_EXPORT'}}}]}};}},nowPlayingItem:{id:'123',privateToken:'NEVER_EXPORT'},
 _playbackController:{services:{store:{storekit:{hasMusicSubscription:async()=>true}}}},
 services:{assetResolver:{resolveCatalogSongAsset:async(item,options)=>{
  assert.equal(options.hlsEnhancedAsset,true);assert.equal(options.subscription,true);
  return {assetURL:host+'/master?session=NEVER_EXPORT',keyServerURL:host+'/license',keyCertURL:host+'/certificate'};
 }},license:{requestLicense:async(item,params)=>{requests.push(params);return {status:0,license:'b3BhcXVl'};},revokeLicense:async()=>{}}}};
const context=vm.createContext({location:{origin:'https://music.apple.com'},window:{MusicKit:{getInstance:()=>music}},
 crypto:{randomUUID:()=>String(Math.random())},URL,TextEncoder,TextDecoder,Uint8Array,Map,AbortController,setTimeout,clearTimeout,
 atob:s=>Buffer.from(s,'base64').toString('binary'),btoa:s=>Buffer.from(s,'binary').toString('base64'),
 fetch:async(url,options)=>{
  const u=new URL(url);assert.equal(u.origin,host);assert.equal(options.credentials,'omit');
  const file=files[u.pathname];assert(file,u.pathname);const raw=file();let bytes=typeof raw==='string'?new TextEncoder().encode(raw):raw;
  const range=options.headers.Range;let status=200;
  if(range){const m=/bytes=(\d+)-(\d+)/.exec(range);assert(m);bytes=bytes.slice(Number(m[1]),Number(m[2])+1);status=206;}
  let read=false;return {ok:true,status,body:{getReader:()=>({read:async()=>read?{done:true}:(read=true,{done:false,value:bytes}),cancel:async()=>{}})}};
 }});
vm.runInContext(fs.readFileSync('src/apple_web_host/spatial_source.js','utf8'),context);
const call=params=>context.emberboxSpatialSource(params);
(async()=>{
 const prepared=await call({action:'prepare'});
 assert.equal(prepared.segments.length,1);assert.equal(prepared.segments[0].keyIndex,1);
 assert.equal(prepared.licences.length,2);assert(!JSON.stringify(prepared).includes('NEVER_EXPORT'));
 const id=prepared.contextId;
 const first=await call({action:'segment',contextId:id,index:0,offset:0});
 assert.equal(first.total,120);assert.deepEqual(Buffer.from(first.data,'base64'),Buffer.from(Uint8Array.from({length:120},(_,i)=>i)));
 const rest=await call({action:'segment',contextId:id,index:0,offset:100});assert.equal(Buffer.from(rest.data,'base64').length,20);
 await call({action:'license',contextId:id,index:1,challenge:'Y2hhbGxlbmdl'});
 assert(requests.at(-1).keyuri.endsWith(key(1)),'License must correspond to the active media key, not initialization key');
 await assert.rejects(call({action:'segment',contextId:id,index:-1}),/INVALID_ARGUMENTS/);
 await assert.rejects(call({action:'segment',contextId:id,index:0,offset:120}),/INVALID_ARGUMENTS/);
 await call({action:'close',contextId:id});await assert.rejects(call({action:'segment',contextId:id,index:0}),/STALE/);
 noAtmos=true;await assert.rejects(call({action:'prepare'}),/NO_ATMOS_ASSET/);
 const stereo=await call({action:'prepare',allowStereo:true,kind:'songs',id:'789'});
 assert.equal(stereo.codec,'aac');assert.equal(stereo.metadata.id,'789');assert.equal(stereo.metadata.title,'Next song');
 assert(!JSON.stringify(stereo).includes('NEVER_EXPORT'));await call({action:'close',contextId:stereo.contextId});
 const count=requests.length;
 const inspection=await call({action:'inspect',kind:'songs',id:'789',extended:true});
 assert.equal(inspection.variants[0].codecs[0],'alac');assert.equal(inspection.protection[0].fairplay,true);
 assert.equal(inspection.protection[0].widevine,false);assert.equal(requests.length,count,'Format inspection must not request a license');
 assert(!JSON.stringify(inspection).includes('NEVER_EXPORT'));assert.equal(context.window.__emberSpatialContexts.size,0);
 files['/lossless.m3u8']=()=>`#EXTM3U\n#EXT-X-KEY:METHOD=SAMPLE-AES,KEYFORMAT="com.apple.streamingkeydelivery",URI="skd://itunes.apple.com/P000000000/s1/e1"\n#EXT-X-MAP:URI="audio.mp4",BYTERANGE="100@0"\n#EXT-X-KEY:METHOD=SAMPLE-AES,KEYFORMAT="com.apple.streamingkeydelivery",URI="skd://itunes.apple.com/P123456789/s1/e1"\n#EXTINF:10,\n#EXT-X-BYTERANGE:20@100\naudio.mp4\n#EXT-X-ENDLIST\n`;
 const lossless=await call({action:'prepare',fairplay:true,allowStereo:true,kind:'songs',id:'789'});
 assert.equal(lossless.codec,'alac');assert.equal(lossless.drm,'fairplay');assert.equal(lossless.certificate,'');
 assert.equal(lossless.segments[0].keyIndex,1);assert.equal(lossless.licences.length,2);
 assert.equal(lossless.licences[1].uri,'skd://itunes.apple.com/P123456789/s1/e1');
 assert(!JSON.stringify(lossless).includes('NEVER_EXPORT'));assert.equal(requests.length,count);
 await call({action:'close',contextId:lossless.contextId});
 noAtmos=false;
 const spatial=await call({action:'prepare',fairplay:true,kind:'songs',id:'789'});
 assert.equal(spatial.codec,'eac3','Atmos retains priority over the optional stereo Lossless path');
 await call({action:'close',contextId:spatial.contextId});
 music.isAuthorized=false;await assert.rejects(call({action:'prepare'}),/SIGN_IN_REQUIRED/);
 console.log('PASS spatial source: enhanced rendition, key rotation, ranges, bounds, stale contexts and private URL/token isolation');
})().catch(e=>{console.error(e);process.exitCode=1;});
