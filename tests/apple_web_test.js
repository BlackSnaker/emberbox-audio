/* Offline contract checks for the app-owned Apple Music page adapter. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const calls = [];
const resource = {id:'i.fixture',type:'library-songs',attributes:{name:'Fixture',artistName:'Artist',
  durationInMillis:180000,artwork:{url:'https://example.invalid/{w}x{h}.jpg'},playParams:{id:'i.fixture'}},
  privateToken:'NEVER_EXPORT',relationships:{account:{credentials:'NEVER_EXPORT'}}};
const music = {isAuthorized:true,isPlaying:false,currentPlaybackTime:12,currentPlaybackDuration:180,
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
  window:{MusicKit:{getInstance:()=>music}},navigator:{},
  document:{querySelectorAll:()=>[],querySelector:()=>null},URL});
vm.runInContext(fs.readFileSync('src/apple_web_host/page.js','utf8'),context);
const call = (method,params={})=>context.emberboxAppleCommand({method,params});
(async()=>{
  let result = await call('status');
  assert.equal(result.title,'Fixture');assert.equal(result.playing,false);
  assert(!JSON.stringify(result).includes('NEVER_EXPORT'));
  result = await call('browse',{category:'songs'});
  assert.equal(calls.at(-1).path,'/v1/me/library/songs');
  assert.equal(result.items[0].uri,'apple:library-songs:i.fixture');
  assert(!JSON.stringify(result).includes('NEVER_EXPORT'));
  await call('tracks',{kind:'library-playlists',id:'p.fixture'});
  assert.equal(calls.at(-1).path,'/v1/me/library/playlists/p.fixture/tracks');
  await call('search',{term:'Evening'});
  assert.equal(calls.at(-1).path,'/v1/catalog/us/search');
  assert.equal(calls.at(-1).query.term,'Evening');
  await call('play',{kind:'library-songs',id:'i.fixture'});
  assert.equal(calls.at(-2).queue.song,'i.fixture');assert.equal(calls.at(-1),'play');
  await call('play',{kind:'songs',id:'456',queue:['123','456']});
  assert.equal(calls.at(-2).queue.startWith,1);
  assert.deepEqual(Array.from(calls.at(-2).queue.songs),['123','456']);
  await call('transport',{action:'pause'});assert.equal(calls.at(-1),'pause');
  await call('transport',{action:'toggle'});assert.equal(calls.at(-1),'play');
  await call('seek',{position:25});assert.equal(calls.at(-1).seek,25);
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
