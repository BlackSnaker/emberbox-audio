/* Offline official-page artist navigation: no playback or authentication export. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const calls=[];const location={origin:'https://music.yandex.ru',pathname:'/',search:''};
const store={user:{isAuthorized:true,hasPlus:true,token:'NEVER_EXPORT'},sonataState:{
  entityMeta:{id:'123',title:'Original song',mainAlbum:{id:456,title:'Original Album'},artists:[{id:100,name:'Original Artist'}]},isPlaying:true,duration:180,position:12}};
const router={push(route){const u=new URL(route,location.origin);location.pathname=u.pathname;location.search=u.search;calls.push(route);},replace(){},prefetch(){}};
const rootFiber={__reactFiber$fixture:{memoizedProps:{value:store},return:{memoizedProps:{value:router}}}};
const artistLink={getAttribute:()=>'/artist/100',textContent:'Original Artist',closest:()=>null};
const albumCard={querySelector:s=>s.includes('ALBUM_TITLE')?{textContent:'Original Album'}:s==='img'?{src:'https://avatars.yandex.net/cover/400x400'}:null};
const albumLink={getAttribute:()=>'/album/456',textContent:'Original Album',closest:()=>albumCard};
const heading={textContent:'Original Artist'};
const main={querySelector:s=>s==='h1'?heading:s.includes('Empty')?{textContent:'No rows'}:s.includes('a[href*=')?albumLink:
  s.includes('ArtistDescription')?{textContent:'Original biography'}:null,
  querySelectorAll:s=>s==='a[href*="/album/"]'?[albumLink]:s==='a[href*="/artist/"]'?[artistLink]:[]};
const document={readyState:'complete',body:{textContent:'Music'},querySelector:s=>s==='main'?main:null,
  querySelectorAll:s=>s.includes('PLAYERBAR_DESKTOP')||s.startsWith('main,')?[rootFiber]:[]};
Object.defineProperty(document,'cookie',{get(){throw Error('Credentials must not be read');}});
const context=vm.createContext({window:{__emberboxPlaybackAllowed:true},document,location,navigator:{},URL,Map,setTimeout});
vm.runInContext(fs.readFileSync('src/apple_web_host/yandex.js','utf8'),context);
const call=(method,params={})=>context.emberboxYandexCommand({method,params});
(async()=>{
  assert.equal((await call('status')).artists[0].id,'100');
  let result=await call('artist',{songId:'123'});
  assert.equal(result.artist.id,'100');assert.equal(result.artist.bio,'Original biography');
  assert.equal(calls.at(-1),'/artist/100');assert.equal(result.sections[1].items[0].id,'456');
  assert(!JSON.stringify(result).includes('NEVER_EXPORT'));
  result=await call('artistSection',{id:'100',section:'compilations'});
  assert.equal(result.items.length,0,'Never label all albums as compilations');
  result=await call('artistSection',{id:'100',section:'albums'});assert.equal(result.items[0].uri,'yandex:album:456');
  assert.equal((await call('status')).albumId,'456');
  result=await call('release',{songId:'123'});assert.equal(result.release.id,'456');assert.equal(calls.at(-1),'/album/456');
  await assert.rejects(call('release',{songId:'122'}),/NOT_FOUND/);
  // Without a source-owned SPA navigator, artist browsing must not request a
  // whole-page reload that would stop the source's current audio.
  delete context.window.__emberboxYandex.router;delete rootFiber.__reactFiber$fixture.return;
  await assert.rejects(call('artist',{id:'101'}),/ADAPTER_UNAVAILABLE/);
  for(const id of ['../account','https://evil.invalid/','123?token=secret']) {
    await assert.rejects(call('artist',{id}),/INVALID_ARGUMENTS/);
    await assert.rejects(call('release',{id}),/INVALID_ARGUMENTS/);
  }
  assert(calls.every(route=>/^\/(artist|album)\//.test(route)),'Browsing must not execute a playback command');
  console.log('PASS Yandex artist identity, release cards, missing-category honesty and playback-preserving navigation');
})().catch(error=>{console.error(error);process.exitCode=1;});
