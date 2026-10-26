/* Offline contract checks for the app-owned Apple Music page adapter. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const calls = [];
const resource = {id:'i.fixture',type:'library-songs',attributes:{name:'Fixture',artistName:'Artist',
  durationInMillis:180000,artwork:{url:'https://example.invalid/{w}x{h}.jpg'},playParams:{id:'i.fixture'}},
  privateToken:'NEVER_EXPORT',relationships:{account:{credentials:'NEVER_EXPORT'}}};
const music = {isAuthorized:true,isPlaying:false,bitrate:64,currentPlaybackTime:12,currentPlaybackDuration:180,
  nowPlayingItem:resource,storefrontId:'us',api:{music:async(path,query)=>{
    calls.push({path,query});return {data:path.includes('/catalog/')
      ? {results:{songs:{data:[{...resource,id:'123',type:'songs'}]}}}
      : {data:[resource],next:'more'}};
  }},setQueue:async value=>calls.push({queue:value}),
  play:async()=>{calls.push('play');music.isPlaying=true;},
  pause:async()=>{calls.push('pause');music.isPlaying=false;},
  skipToNextItem:async()=>calls.push('next'),skipToPreviousItem:async()=>calls.push('previous'),
  seekToTime:async value=>calls.push({seek:value})};
const context = vm.createContext({location:{origin:'https://music.apple.com'},
  window:{MusicKit:{getInstance:()=>music,PlaybackBitrate:{STANDARD:64,HIGH:256}}},navigator:{},
  document:{querySelectorAll:()=>[],querySelector:()=>null},URL,setTimeout,clearTimeout});
vm.runInContext(fs.readFileSync('src/apple_web_host/page.js','utf8'),context);
const call = (method,params={})=>context.emberboxAppleCommand({method,params});
(async()=>{
  let result = await call('status');
  assert.equal(result.title,'Fixture');assert.equal(result.playing,false);
  assert.equal(music.bitrate,256);assert.equal(result.qualityPreference.applied,true);
  // A paused queue restore has a real song before MusicKit populates its
  // nowPlayingItem or duration. The placeholder must not mask that song.
  music.nowPlayingItem={id:'-1'};music.queue={position:0,items:[resource]};
  music.currentPlaybackDuration=0;
  result=await call('status');
  assert.equal(result.id,'i.fixture');assert.equal(result.title,'Fixture');assert.equal(result.duration,180);
  assert.equal(result.playing,false);assert.equal(result.audioQuality,undefined);
  music.nowPlayingItem={};
  assert.equal((await call('status')).id,'i.fixture');
  music.nowPlayingItem=resource;delete music.queue;music.currentPlaybackDuration=180;
  music.bitrate=512;
  await call('status');assert.equal(music.bitrate,512,'A future higher quality must not be lowered');
  resource.attributes.playParams.catalogId='12345';resource.attributes.url='https://music.apple.com/us/album/fixture/45678?i=12345';
  result=await call('status');assert.equal(result.catalogId,'12345');
  assert.equal(result.url,'https://music.apple.com/us/album/fixture/45678');
  assert(!JSON.stringify(result).includes('NEVER_EXPORT'));
  resource.attributes.audioVariants=['dolby-atmos','lossless','SECRET_INVALID'];
  result=await call('status');
  assert.deepEqual(Array.from(result.availableFormats),['dolby-atmos','lossless']);
  assert.equal(result.audioQuality,undefined,'Catalogue variants are not decoder evidence');
  resource.attributes.audioTraits=['atmos','hi-res-lossless','lossless','lossy-stereo','atmos',{},'SECRET_INVALID'];
  result=await call('status');
  assert.deepEqual(Array.from(result.availableFormats),['dolby-atmos','lossless','hi-res-lossless','lossy-stereo']);
  delete resource.attributes.audioVariants;
  result=await call('status');
  assert.deepEqual(Array.from(result.availableFormats),['dolby-atmos','hi-res-lossless','lossless','lossy-stereo']);
  assert.equal(result.audioQuality,undefined,'Website traits do not prove Atmos playback');
  resource.attributes.audioTraits=['surround'];
  assert.deepEqual(Array.from((await call('status')).availableFormats),['dolby-audio']);
  delete resource.attributes.audioTraits;
  // Missing storefront overrides use the same catalogue default as browsing.
  // A slow previous-song result may not label the newly playing song.
  const qualityApi=music.api.music;
  let releaseVariants;
  music.api.music=async(path,query)=>{calls.push({path,query});return await new Promise(resolve=>{releaseVariants=resolve;});};
  music.storefrontId=undefined;resource.attributes.playParams.catalogId='7001';
  await call('status');await Promise.resolve();
  assert.equal(calls.at(-1).path,'/v1/catalog/us/songs/7001');
  const oldVariants=releaseVariants;
  resource.attributes.playParams.catalogId='7002';
  await call('status');await Promise.resolve();
  oldVariants({data:{data:[{attributes:{audioTraits:['atmos']}}]}});
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.deepEqual(Array.from((await call('status')).availableFormats),[]);
  releaseVariants({data:{data:[{attributes:{audioTraits:['lossless','surround']}}]}});
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.deepEqual(Array.from((await call('status')).availableFormats),['lossless','dolby-audio']);
  resource.attributes.playParams.catalogId='7003';
  assert.deepEqual(Array.from((await call('status')).availableFormats),[]);
  releaseVariants({data:{data:[]}});
  music.api.music=qualityApi;music.storefrontId='us';
  result = await call('browse',{category:'songs'});
  assert.equal(calls.at(-1).path,'/v1/me/library/songs');
  assert.equal(result.items[0].uri,'apple:library-songs:i.fixture');
  assert(!JSON.stringify(result).includes('NEVER_EXPORT'));
  await call('tracks',{kind:'library-playlists',id:'p.fixture'});
  assert.equal(calls.at(-1).path,'/v1/me/library/playlists/p.fixture/tracks');
  await call('search',{term:'Evening'});
  assert.equal(calls.at(-1).path,'/v1/catalog/us/search');
  assert.equal(calls.at(-1).query.term,'Evening');
  await call('search',{term:'feel good',types:'playlists'});
  assert.equal(calls.at(-1).query.types,'playlists');
  assert.equal(calls.at(-1).query.term,'feel good');
  await assert.rejects(call('search',{term:'anything',types:'accounts'}));
  await call('play',{kind:'library-songs',id:'i.fixture'});
  assert.equal(calls.at(-2).queue.song,'i.fixture');assert.equal(calls.at(-1),'play');
  await call('play',{kind:'songs',id:'456',queue:['123','456']});
  assert.equal(calls.at(-2).queue.startWith,1);
  assert.deepEqual(Array.from(calls.at(-2).queue.songs),['123','456']);
  await call('transport',{action:'pause'});assert.equal(calls.at(-1),'pause');
  await call('transport',{action:'toggle'});assert.equal(calls.at(-1),'play');
  await call('seek',{position:25});assert.equal(calls.at(-1).seek,25);
  const queueCalls=calls.filter(value=>value?.queue).length;
  await call('play',{kind:'songs',id:'456',native:true,metadata:{title:'Native song',artist:'Native artist',
    album:'Native album',catalogId:'456',duration:240,availableFormats:['lossless']}});
  result=await call('status');assert.equal(result.id,'456');assert.equal(result.title,'Native song');
  assert.equal(result.playing,false);assert.equal(result.audioQuality,undefined);
  assert.equal(calls.filter(value=>value?.queue).length,queueCalls,'Native metadata sync must not set another SDK queue');
  context.window.__emberboxRestoredTrack=null;
  const savedApi=music.api.music;
  const savedQueue=music.setQueue;
  let restoreMetadata;
  music.setQueue=async()=>{music.nowPlayingItem={id:'-1'};music.currentPlaybackDuration=0;};
  music.api.music=async()=>await new Promise(resolve=>{restoreMetadata=resolve;});
  await call('play',{kind:'library-songs',id:'i.fixture',position:42,paused:true});
  result=await call('status');
  assert.equal(result.id,'i.fixture');assert.equal(result.playing,false);assert.equal(result.position,42);
  assert.equal(result.audioQuality,undefined,'Restored catalogue metadata is not decoder evidence');
  restoreMetadata({data:{data:[resource]}});await new Promise(resolve=>setTimeout(resolve,0));
  result=await call('status');assert.equal(result.title,'Fixture');assert.equal(result.duration,180);
  // A late metadata request for a previous paused queue cannot replace the new song.
  await call('play',{kind:'library-songs',id:'i.old',paused:true});
  const oldRestore=restoreMetadata;
  await call('play',{kind:'library-songs',id:'i.new',paused:true});
  oldRestore({data:{data:[resource]}});await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal((await call('status')).id,'i.new');
  restoreMetadata({data:{data:[]}});
  music.api.music=savedApi;music.setQueue=savedQueue;music.nowPlayingItem=resource;music.currentPlaybackDuration=180;
  context.window.__emberboxRestoredTrack=null;context.window.__emberboxRestorePosition=0;
  // The DJ sees typed catalogue resources; account and relationship secrets stay inside MusicKit.
  const originalApi=music.api.music;
  music.api.music=async(path,query)=>{
    calls.push({path,query});
    if(path==='/v1/me/recommendations')return {data:{data:[{id:'recommendation',type:'personal-recommendations',
      attributes:{privateToken:'NEVER_EXPORT'},relationships:{contents:{data:[
        {id:'pl.fixture',type:'playlists',attributes:{name:'Personal chill',genreNames:['Ambient']}},
        {id:'invalid/../account',type:'playlists',attributes:{name:'Invalid'}},
        {id:'123',type:'songs',attributes:{name:'Real song',artistName:'Artist'}},
        {id:'user',type:'accounts',attributes:{name:'NEVER_EXPORT'}}]}}}]}};
    if(path==='/v1/me/recent/played/tracks')return {data:{data:[resource]}};
    return {data:{data:[{...resource,id:'123',type:'songs'}]}};
  };
  result=await call('browse',{category:'dj'});
  assert.equal(result.personal,true);assert.equal(result.items.length,1);assert.equal(result.items[0].id,'pl.fixture');
  assert.equal(result.tracks[0].uri,'apple:songs:123');assert.equal(result.recent[0].uri,'apple:library-songs:i.fixture');
  assert(!JSON.stringify(result).includes('NEVER_EXPORT'));
  await call('tracks',{kind:'playlists',id:'pl.fixture'});
  assert.equal(calls.at(-1).path,'/v1/catalog/us/playlists/pl.fixture/tracks');
  music.api.music=async(path)=>{if(path.includes('recommendations'))throw Error('unavailable');return {data:{data:[resource]}};};
  result=await call('browse',{category:'dj'});assert.equal(result.partial,true);assert.equal(result.recent.length,1);
  music.api.music=originalApi;
  // A queue request can finish after the user switches sources.
  music.setQueue=async()=>{context.window.__emberboxPlaybackAllowed=false;};
  const starts=calls.filter(value=>value==='play').length;
  await call('play',{kind:'library-songs',id:'i.fixture'});
  await call('transport',{action:'toggle'});
  assert.equal(calls.filter(value=>value==='play').length,starts);
  await assert.rejects(call('browse',{category:'account'}));
  await assert.rejects(call('play',{kind:'songs',id:'../../account'}));
  await assert.rejects(call('seek',{position:-1}));
  await assert.rejects(call('executeJavaScript',{code:'anything'}));
  music.isAuthorized=false;
  assert.equal((await call('status')).authorized,false);
  await assert.rejects(call('browse'),/Sign in/);
  context.window.MusicKit=undefined;
  result=await call('status');assert.equal(result.ready,false);assert.equal(result.playing,false);
  console.log('PASS native Apple library, search, queue, transport, source switching and private metadata');
})().catch(error=>{console.error(error);process.exitCode=1;});
