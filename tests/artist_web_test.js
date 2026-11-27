/* Real Apple artist commands with bounded offline catalogue resources. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const requests=[],transport=[],deadlines=[];
let collaboration=false,missingRelationship=false,latestOnly=false,mismatchArtist=false,hangProfile=false,quickTimers=false,missingAlbum=false;
const viewBehavior=new Map();
let catalogueNext,failCatalogue=false,djMode=false;
const artist=id=>({id:String(id),type:'artists',attributes:{name:'Emberbox Sessions '+id,
  artwork:{url:'https://example.invalid/{w}x{h}.jpg'},genreNames:['Alternative'],
  editorialNotes:{standard:'<p>Original fixture biography &amp; story.</p>'},
  url:'https://music.apple.com/us/artist/fixture/'+id},privateToken:'NEVER_EXPORT'});
const song=id=>({id:String(id),type:'songs',attributes:{name:'Original song '+id,artistName:'Emberbox Sessions',composerName:'Fixture Composer',
  durationInMillis:180000,playParams:{id:String(id)},artwork:{url:'https://example.invalid/{w}x{h}.jpg'}},
  relationships:{artists:{data:missingRelationship?[]:[artist(100),...(collaboration?[artist(101)]:[])]},
    albums:{data:missingAlbum?[]:[{id:'456',type:'albums'}]}}});
const album=id=>({id:String(id),type:'albums',attributes:{name:'Original album '+id,artistName:'Emberbox Sessions',
  releaseDate:'2026-10-23',trackCount:3,isCompilation:id===457,isSingle:false,playParams:{id:String(id)},
  artwork:{url:'https://example.invalid/{w}x{h}.jpg'},copyright:'Original fixture © Emberbox',
  editorialNotes:{standard:'<p>Original liner notes.</p>'}},relationships:{artists:{data:[artist(100)]},tracks:{data:[song(123),
    {...song(124),attributes:{...song(124).attributes,playParams:undefined}},{id:'999',type:'music-videos',attributes:{name:'Not an audio song'}}],
    next:'/v1/catalog/us/albums/'+id+'/tracks?offset=100'}}});
const release=(id,attributes={})=>({...album(id),attributes:{...album(id).attributes,...attributes}});
const catalogue=Array.from({length:317},(_,i)=>release(2000+i,{name:'Same title',isSingle:i%3===0,isCompilation:i%3===1}));
const viewData={
  'top-songs':[song(123),song(124)],'latest-release':[album(456)],
  'full-albums':[album(456),album(459)],'singles':[release(460,{isSingle:true})],
  'featured-albums':[album(461)],'compilation-albums':[album(457)],
  'appears-on-albums':[release(462,{artistName:'A source-confirmed collaboration'})]
};
const music={isAuthorized:true,bitrate:256,storefrontId:'us',api:{music:async(path,query)=>{
  requests.push({path,query});let response;
  if(path.endsWith('/search'))response={results:{artists:{data:djMode?
    [{...artist(100),attributes:{...artist(100).attributes,name:'Daft Punk',genreNames:['Electronic']}},artist(101)]:[artist(100),artist(101)]}}};
  else if(/\/songs\/[^/]+\/catalog$/.test(path)||/\/songs\/\d+$/.test(path))response={data:[song(123)]};
  else if(/\/artists\/\d+\/albums$/.test(path)){
    if(failCatalogue)throw Error('Fixture network error');
    const start=query.offset||0;
    response={data:catalogue.slice(start,start+100),next:catalogueNext!==undefined?catalogueNext:start+100<catalogue.length?path+'?offset='+(start+100):null};
  }
  else if(/\/artists\/\d+$/.test(path)){
    if(hangProfile)return new Promise(()=>{});
    response={data:[{...artist(mismatchArtist?999:path.split('/').at(-1)),views:{
      ...(!latestOnly?{'top-songs':{data:viewData['top-songs']}}:{}),
      'latest-release':{data:viewData['latest-release']}}}]};
  }
  else if(path.includes('/view/')){
    const view=path.split('/').at(-1),behavior=viewBehavior.get(view);
    if(djMode&&view==='similar-artists')return {data:{data:[artist(100),...Array.from({length:8},(_,i)=>artist(200+i)),artist('../account')]}};
    if(djMode&&view==='top-songs'){
      const base=Number(path.split('/').at(-3))*1000;
      return {data:{data:Array.from({length:8},(_,i)=>song(base+i))}};
    }
    if(behavior==='error')throw Error('Fixture optional view unavailable');
    if(behavior==='hang')return new Promise(()=>{});
    response={data:behavior===undefined?viewData[view]:behavior,next:query.offset?null:path+'?offset=24'};
  }
  else if(/\/albums\/\d+\/tracks$/.test(path))response={data:[song(125)],next:null};
  else if(/\/albums\/\d+$/.test(path)){
    const value=album(Number(path.split('/').at(-1)));
    if(query['include[songs]']!=='artists')delete value.relationships.artists;
    response={data:[value]};
  }
  else throw Error('Unexpected path '+path);
  return {data:response};
}},setQueue:async value=>transport.push(value),play:async()=>transport.push('play'),pause:async()=>transport.push('pause')};
const context=vm.createContext({location:{origin:'https://music.apple.com'},
  window:{MusicKit:{getInstance:()=>music,PlaybackBitrate:{HIGH:256}}},navigator:{},
  document:{querySelectorAll:()=>[],querySelector:()=>null},URL,
  setTimeout:(callback,ms)=>{deadlines.push(ms);return setTimeout(callback,quickTimers?Math.min(ms,25):ms);},clearTimeout});
vm.runInContext(fs.readFileSync('src/apple_web_host/page.js','utf8'),context);
const call=(method,params={})=>context.emberboxAppleCommand({method,params});
const section=(result,id)=>result.sections.find(s=>s.id===id);
(async()=>{
  let result=await call('artist',{songId:'123',name:'Wrong namesake'});
  assert.equal(requests[0].path,'/v1/catalog/us/songs/123');
  assert.equal(result.artist.id,'100');assert.equal(result.artist.name,'Emberbox Sessions 100');
  assert.equal(result.artist.image,'https://example.invalid/800x800.jpg');
  assert.equal(section(result,'top-songs').items[0].uri,'apple:songs:123');
  assert.equal(section(result,'albums').items.length,2);
  assert.equal(section(result,'singles').items[0].isSingle,true);
  assert.equal(section(result,'compilations').items[0].isCompilation,true);
  assert.equal(section(result,'featured-albums').items[0].id,'461');
  assert.equal(section(result,'appears').items[0].id,'462');
  assert(!requests.some(r=>r.path.endsWith('/view/top-songs')),'Do not duplicate an included, populated view');
  assert(requests.filter(r=>r.path.includes('/view/')).length<=7,'Initial view requests stay bounded');
  assert(requests.filter(r=>r.path.includes('/view/')).every(r=>r.query.limit<=10));
  assert(!JSON.stringify(result).includes('NEVER_EXPORT'));
  // Real failure mode: MusicKit includes latest-release but silently omits
  // top-songs. Direct, exact-artist view endpoints still populate the overview.
  latestOnly=true;let start=requests.length;
  result=await call('artist',{id:'100'});
  assert.equal(section(result,'top-songs').items.length,2);
  assert.equal(section(result,'albums').items.length,2);
  assert(requests.slice(start).some(r=>r.path==='/v1/catalog/us/artists/100/view/top-songs'));
  assert(requests.slice(start).every(r=>r.path.includes('/artists/100')),'Never search or switch artist to fill shelves');
  // Independent optional failures keep already available content. A stalled
  // request must not hold the whole card until the bridge's 20-second timeout.
  viewBehavior.set('compilation-albums','error');viewBehavior.set('featured-albums','hang');quickTimers=true;
  start=Date.now();result=await call('artist',{id:'100'});
  assert(Date.now()-start<1000,'Optional deadline returns the usable partial profile promptly');
  assert.equal(section(result,'featured-albums').unavailable,true);
  assert.equal(section(result,'compilations').unavailable,true);
  assert.equal(section(result,'albums').items.length,2);
  assert.equal(section(result,'top-songs').items.length,2);
  assert.equal(section(result,'latest-release').items.length,1);
  assert(deadlines.every(ms=>ms>0&&ms<=6500));
  viewBehavior.clear();quickTimers=false;
  // Empty, malformed and wrong-resource responses stay honest. Do not label a
  // music video as a song, or a single/compilation as a full album.
  viewBehavior.set('top-songs',[song(123),song(123),{...song(124),type:'music-videos'},null]);
  viewBehavior.set('full-albums',[album(456),album(457),release(460,{isSingle:true}),album(456),
    {...album(463),id:'../invalid'},...Array.from({length:30},(_,i)=>album(500+i))]);
  viewBehavior.set('singles',[]);viewBehavior.set('appears-on-albums',{unexpected:'not an array'});
  result=await call('artist',{id:'100'});
  assert.equal(section(result,'top-songs').items.length,1);
  assert.equal(section(result,'albums').items.length,8,'Initial album shelf has a strict payload limit');
  assert(section(result,'albums').items.every(v=>!v.isCompilation&&!v.isSingle));
  assert.equal(section(result,'singles').items.length,0);
  assert.equal(section(result,'singles').unavailable,undefined,'An empty successful view is not a failed request');
  assert.equal(section(result,'appears').items.length,0);
  assert.equal(section(result,'appears').unavailable,true,'A malformed response is not claimed to be an empty catalogue');
  viewBehavior.clear();latestOnly=false;
  mismatchArtist=true;await assert.rejects(call('artist',{id:'100'}),/NOT_FOUND/);mismatchArtist=false;
  hangProfile=true;quickTimers=true;
  await assert.rejects(call('artist',{id:'100'}),/TIMEOUT/);
  hangProfile=false;quickTimers=false;
  collaboration=true;
  result=await call('artist',{songId:'123'});assert.equal(result.choices.length,2);assert.equal(result.artist,undefined);
  assert.equal((await call('artist',{id:result.choices[1].id})).artist.id,'101');
  result=await call('credits',{id:'123'});
  assert.equal(result.composer,'Fixture Composer');
  assert.equal(result.artists.length,2);
  assert.equal(result.artists[0].image,'https://example.invalid/180x180.jpg');
  assert(!JSON.stringify(result).includes('NEVER_EXPORT'));
  await assert.rejects(call('credits',{id:'124'}),/NOT_FOUND/);
  await assert.rejects(call('credits',{id:'../account'}),/INVALID_ARGUMENTS/);
  result=await call('release',{id:'456'});
  assert.equal(result.release.artists.length,1);
  assert.equal(result.items[0].artists[1].id,'101');
  collaboration=false;missingRelationship=true;
  result=await call('artist',{songId:'123',name:'A name with namesakes'});
  assert.equal(result.choices.length,2);assert.equal(result.artist,undefined,'Never silently choose a name search result');
  missingRelationship=false;
  result=await call('artist',{songId:'456',songKind:'albums'});assert.equal(result.artist,undefined);
  assert.equal(requests.at(-1).path,'/v1/catalog/us/albums/456','Album identity must not be looked up as a song');
  result=await call('artistSection',{id:'100',section:'albums'});
  assert.equal(result.items[0].kind,'albums');assert.equal(result.next,24);
  assert.equal(requests.at(-1).path,'/v1/catalog/us/artists/100/view/full-albums');
  await call('artistSection',{id:'100',section:'singles',offset:24});assert.equal(requests.at(-1).query.offset,24);
  // The full relationship must not inherit the curated views or a 200-release
  // client limit. Every edition is retained, even when titles are identical.
  const complete=[];let cursor=0;
  do {
    result=await call('artistSection',{id:'100',section:'discography',offset:cursor,storefront:'us'});
    assert.equal(result.catalog,true);assert.equal(result.storefront,'us');
    assert.equal(requests.at(-1).path,'/v1/catalog/us/artists/100/albums');
    assert.equal(requests.at(-1).query.limit,100);
    complete.push(...result.items);cursor=result.next;
  }while(cursor!==null);
  assert.equal(complete.length,317);assert.equal(new Set(complete.map(v=>v.id)).size,317);
  for(const next of ['/v1/catalog/us/artists/100/albums?offset=0','/v1/catalog/us/artists/999/albums?offset=100',
      '/v1/catalog/gb/artists/100/albums?offset=100','https://evil.invalid/v1/catalog/us/artists/100/albums?offset=100',
      '/v1/catalog/us/artists/100/albums?offset=wrong']) {
    catalogueNext=next;await assert.rejects(call('artistSection',{id:'100',section:'discography'}),/continuation/);
  }
  catalogueNext=undefined;failCatalogue=true;
  await assert.rejects(call('artistSection',{id:'100',section:'discography',offset:200}));
  failCatalogue=false;
  result=await call('artistSection',{id:'100',section:'discography',offset:200});
  assert.equal(result.items.length,100);assert.equal(result.next,300,'A failed page remains retryable');
  await assert.rejects(call('artistSection',{id:'100',section:'discography',offset:-1}));
  await assert.rejects(call('artistSection',{id:'100',section:'discography',storefront:'../account'}));
  await call('artistSection',{id:'100',section:'compilations'});
  assert.equal(requests.at(-1).path,'/v1/catalog/us/artists/100/view/compilation-albums');
  assert.equal((await call('artistSection',{id:'100',section:'featured-albums'})).items[0].id,'461');
  assert.equal((await call('artistSection',{id:'100',section:'top-songs'})).items[0].kind,'songs');
  result=await call('release',{id:'456'});assert.equal(result.release.trackCount,3);
  assert.equal(result.items.length,2);assert.equal(result.items[1].playable,false);assert.equal(result.next,100);
  const beforePage=requests.length;
  result=await call('release',{id:'456',offset:100});assert.equal(result.items[0].id,'125');assert.equal(result.next,null);
  assert.deepEqual(requests.slice(beforePage).map(request=>request.path),['/v1/catalog/us/albums/456/tracks']);
  result=await call('release',{songId:'123',name:'Wrong namesake album'});
  assert.equal(result.release.id,'456');assert.equal(result.release.title,'Original album 456');
  assert.equal(requests.at(-2).path,'/v1/catalog/us/songs/123');assert.equal(requests.at(-2).query.include,'albums');
  result=await call('release',{songId:'i.library',songKind:'library-songs'});
  assert.equal(requests.at(-2).path,'/v1/me/library/songs/i.library/catalog');assert.equal(result.release.id,'456');
  missingAlbum=true;const beforeAlbumMiss=requests.length;
  await assert.rejects(call('release',{songId:'123',name:'Wrong namesake album'}),/NOT_FOUND/);
  assert.equal(requests.length,beforeAlbumMiss+1,'Missing album relationships must not fall back to name search');missingAlbum=false;
  await assert.rejects(call('release',{songId:'../account'}));
  result=await call('artist',{songId:'i.library'});assert.equal(result.artist.id,'100');
  assert(requests.some(r=>r.path==='/v1/me/library/songs/i.library/catalog'));
  for(const id of ['../account','https://evil.invalid/','123?token=secret']) {
    await assert.rejects(call('artist',{id}));await assert.rejects(call('release',{id}));
  }
  await assert.rejects(call('artistSection',{id:'100',section:'account'}));
  djMode=true;
  const beforeDJ=requests.length;
  result=await call('artistSection',{name:'daft punk',section:'dj-similar'});
  assert.equal(result.artist.name,'Daft Punk');assert.equal(result.related.length,4);
  assert.equal(result.items.length,32);assert(result.items.every(s=>s._dj_related==='Daft Punk'));
  assert.equal(new Set(result.items.map(s=>s.id)).size,32);
  assert.equal(requests.length-beforeDJ,6,'One artist search, one relation and four bounded song views');
  assert.equal(requests[beforeDJ+1].path,'/v1/catalog/us/artists/100/view/similar-artists');
  assert(!JSON.stringify(result).includes('NEVER_EXPORT'));
  assert.equal((await call('artistSection',{name:'Unknown act',section:'dj-similar'})).items.length,0);
  djMode=false;
  assert.deepEqual(transport,[],'Browsing must never change playback');
  music.isAuthorized=false;await assert.rejects(call('artist',{id:'100'}),/Sign in/);
  console.log('PASS exact artists, rich bounded overview, missing-view fallback, partial failures/timeouts, strict categories, paging and unchanged transport');
})().catch(error=>{console.error(error);process.exitCode=1;});
