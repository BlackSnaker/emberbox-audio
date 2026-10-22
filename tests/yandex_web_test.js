/* Offline contracts for Yandex's modern player, My Wave and typed commands. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const calls=[];
const store={user:{isAuthorized:true,hasPlus:true,privateToken:'NEVER_EXPORT'},
  sonataState:{entityMeta:{id:'123',title:'Fixture',artistsNames:'Artist',mainAlbum:{title:'Album'},
    coverUri:'avatars.yandex.net/fixture/%%',privateData:'NEVER_EXPORT'},duration:180,position:0,
    isPlaying:true,isVibeContext:false,canMoveForward:true,canMoveBackward:true}};
const engine={togglePause:async()=>calls.push('toggle'),pause:async()=>calls.push('pause'),
  resume:async()=>calls.push('resume'),moveForward:async()=>calls.push('next'),moveBackward:async()=>calls.push('previous'),
  setProgress:async value=>calls.push({seek:value}),playContext:async params=>calls.push({context:params})};
const quality={quality:{value:'balanced'},setQuality(value){this.quality.value=value;}};
store.sonataState.quality='balanced';store.sonataState.setQuality=value=>{store.sonataState.quality=value;};
const location={origin:'https://music.yandex.ru',pathname:'/',search:''};
const router={replace(){},prefetch(){},push(route){const u=new URL(route,location.origin);location.pathname=u.pathname;location.search=u.search;calls.push({route});}};
const fiber={memoizedProps:{value:store},return:{memoizedProps:{value:engine},return:{memoizedProps:{value:router}}}};
fiber.dependencies={firstContext:{memoizedValue:quality}};
const root={__reactFiber$fixture:fiber};
let hoverControls=true;
const control={matches:()=>true,querySelector:()=>null,disabled:false,getAttribute:()=>null,getClientRects:()=>[{}],click:()=>calls.push('click')};
const title={textContent:'Fixture track',matches:()=>true,getAttribute:()=>'/album/456/track/123',
  closest:()=>row,parentElement:null};
const row={isConnected:true,querySelector:selector=>selector.includes('PLAY_BUTTON')?(hoverControls?control:null):selector.includes('TRACK_TITLE')?title:null,
  querySelectorAll:()=>[],parentElement:null};
const playlistTitle={textContent:'Evening playlist',matches:()=>true,getAttribute:()=>'/playlists/fixture-123',closest:()=>({querySelector:()=>({src:'https://avatars.yandex.net/playlist/400x400'})})};
const document={readyState:'complete',body:{textContent:'Музыка'},
  querySelector:selector=>selector.includes('PLAYLIST_TITLE')?playlistTitle:selector.includes('TRACK_TITLE')||selector.includes('a[href*=')?title:
    selector.includes('LIKE_BUTTON')||selector.includes('DISLIKE_BUTTON')?control:null,
  querySelectorAll:selector=>selector.startsWith('main,')||selector.includes('PLAYERBAR_DESKTOP')?[root]:selector.includes('PLAYLIST_TITLE')?[playlistTitle]:selector.includes('TRACK_TITLE')?[title]:[]};
const context=vm.createContext({window:{__emberboxPlaybackAllowed:true},document,location,
  navigator:{mediaSession:{metadata:null,playbackState:'none'}},URL,Map,setTimeout});
vm.runInContext(fs.readFileSync('src/apple_web_host/yandex.js','utf8'),context);
const call=(method,params={})=>context.emberboxYandexCommand({method,params});
(async()=>{
  const status=await call('status');assert.equal(status.authorized,true);assert.equal(status.title,'Fixture');
  assert.equal(status.qualityPreference.applied,true);assert.equal(quality.quality.value,'high_quality');
  assert.equal(store.sonataState.quality,'high_quality');assert.equal(status.audioQuality,undefined);
  assert.equal(status.position,0);assert.equal(status.image,'https://avatars.yandex.net/fixture/400x400');
  assert(!JSON.stringify(status).includes('NEVER_EXPORT'));
  await call('wave');const wave=calls.at(-1).context.contextData;
  assert.equal(wave.type,'vibe');assert.equal(wave.seeds[0],'user:onyourwave');
  assert.equal(wave.interactive,true);assert.equal(wave.includeTracksInResponse,true);
  store.sonataState.isVibeContext=true;
  assert.equal((await call('status')).wave,true);
  store.sonataState.isPlaying=false;
  await call('wave');assert.equal(calls.at(-1),'resume');
  for(const [action,value]of [['toggle','toggle'],['pause','pause'],['next','next'],['previous','previous']]){
    await call('transport',{action});assert.equal(calls.at(-1),value);
  }
  await call('seek',{position:25});assert.equal(calls.at(-1).seek,25);
  await call('feedback',{action:'like'});assert.equal(calls.at(-1),'click');
  await call('feedback',{action:'dislike'});assert.equal(calls.at(-1),'click');
  const search=await call('search',{term:'Evening & dawn'});
  assert.equal(calls.at(-1).route,'/search?text=Evening%20%26%20dawn');
  assert.equal(search.items[0].id,'123');assert.equal(search.items[0].uri,'yandex:track:123');
  assert(!JSON.stringify(search).includes('NEVER_EXPORT'));
  await call('play',{id:'123'});assert.equal(calls.at(-1),'click');
  const collection=await call('browse',{category:'collection'});assert.equal(calls.at(-1).route,'/collection/playlists');
  assert.equal(collection.items[0].kind,'playlist');assert.equal(collection.items[0].id,'/playlists/fixture-123');
  const tracks=await call('tracks',{id:collection.items[0].id});assert.equal(calls.at(-1).route,'/playlists/fixture-123');
  assert.equal(tracks.items[0].id,'123');
  for(const id of ['https://example.invalid/playlists/123','/account','/playlists/../account','javascript:alert(1)'])await assert.rejects(call('tracks',{id}),/INVALID_ARGUMENTS/);
  hoverControls=false;
  const contextParams={contextData:{type:'album',meta:{id:'456'}},queueParams:{entityId:'123:456'}};
  title.__reactFiber$track={memoizedProps:{playContextParams:contextParams}};
  await call('search',{term:'No hover buttons'});
  assert.equal((await call('search',{term:'No hover buttons'})).items.length,1);
  await call('play',{id:'123'});assert.deepEqual(calls.at(-1).context,contextParams);
  hoverControls=true;
  await assert.rejects(call('play',{id:'../../account'}),/INVALID_ARGUMENTS/);
  await assert.rejects(call('seek',{position:-1}),/INVALID_ARGUMENTS/);
  await assert.rejects(call('feedback',{action:'delete'}),/INVALID_ARGUMENTS/);
  await assert.rejects(call('executeJavaScript',{code:'anything'}),/UNSUPPORTED/);
  const starts=calls.filter(value=>value.context||value==='resume'||value==='toggle').length;
  context.window.__emberboxPlaybackAllowed=false;
  quality.quality.value='balanced';store.sonataState.quality='balanced';
  await call('wave');await call('play',{id:'123'});await call('transport',{action:'toggle'});
  assert.equal(quality.quality.value,'balanced','Inactive source must not change quality');
  assert.equal(calls.filter(value=>value.context||value==='resume'||value==='toggle').length,starts);
  await call('transport',{action:'pause'});assert.equal(calls.at(-1),'pause');
  context.window.__emberboxPlaybackAllowed=true;
  store.user.hasPlus=false;
  assert.equal((await call('status')).qualityPreference.reason,'subscription');
  assert.equal(quality.quality.value,'balanced');
  await assert.rejects(call('wave'),/SUBSCRIPTION_REQUIRED/);
  store.user.isAuthorized=false;
  assert.equal((await call('status')).authorized,false);
  await assert.rejects(call('wave'),/SIGN_IN_REQUIRED/);
  document.body.textContent='Яндекс Музыка недоступна в вашем регионе';
  assert.equal((await call('status')).regionBlocked,true);
  await assert.rejects(call('wave'),/REGION_UNAVAILABLE/);
  document.body.textContent='Музыка';store.user.isAuthorized=true;store.user.hasPlus=true;
  root.__reactFiber$fixture={memoizedProps:{},dependencies:{firstContext:{memoizedValue:store,next:{memoizedValue:engine,next:{memoizedValue:router}}}}};
  delete context.window.__emberboxYandex;
  assert.equal((await call('status')).capabilities.player,true);
  assert.equal((await call('status')).authorized,true);
  store.user.isAuthorized=false;
  const signedIn={...store,user:{isAuthorized:true,hasPlus:true},sonataState:{...store.sonataState,entityMeta:{...store.sonataState.entityMeta,title:'After login'}}};
  root.__reactFiber$fixture.dependencies.firstContext.memoizedValue=signedIn;
  assert.equal((await call('status')).title,'After login');assert.equal((await call('status')).authorized,true);
  delete context.window.__emberboxYandex;
  root.__reactFiber$fixture={memoizedProps:{value:signedIn},return:{memoizedProps:{value:engine}}};
  await assert.rejects(call('browse',{category:'collection'}),error=>error.emberboxRoute==='/collection/playlists');
  location.origin='https://example.invalid';
  await assert.rejects(call('status'),/NOT_READY/);
  console.log('PASS Yandex My Wave, metadata privacy, search, reactions, controls and source switching');
})().catch(error=>{console.error(error);process.exitCode=1;});
