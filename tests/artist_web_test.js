/* Real Apple artist commands with bounded offline catalogue resources. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const requests=[],transport=[];let collaboration=false,missingRelationship=false;
const artist=id=>({id:String(id),type:'artists',attributes:{name:'Emberbox Sessions '+id,
  artwork:{url:'https://example.invalid/{w}x{h}.jpg'},genreNames:['Alternative'],
  editorialNotes:{standard:'<p>Original fixture biography &amp; story.</p>'},
  url:'https://music.apple.com/us/artist/fixture/'+id},privateToken:'NEVER_EXPORT'});
const song=id=>({id:String(id),type:'songs',attributes:{name:'Original song '+id,artistName:'Emberbox Sessions',
  durationInMillis:180000,playParams:{id:String(id)},artwork:{url:'https://example.invalid/{w}x{h}.jpg'}},
  relationships:{artists:{data:missingRelationship?[]:[artist(100),...(collaboration?[artist(101)]:[])]}}});
const album=id=>({id:String(id),type:'albums',attributes:{name:'Original album '+id,artistName:'Emberbox Sessions',
  releaseDate:'2026-10-23',trackCount:3,isCompilation:id===457,isSingle:false,playParams:{id:String(id)},
  artwork:{url:'https://example.invalid/{w}x{h}.jpg'},copyright:'Original fixture © Emberbox',
  editorialNotes:{standard:'<p>Original liner notes.</p>'}},relationships:{tracks:{data:[song(123),
    {...song(124),attributes:{...song(124).attributes,playParams:undefined}},{id:'999',type:'music-videos',attributes:{name:'Not an audio song'}}],
    next:'/v1/catalog/us/albums/'+id+'/tracks?offset=100'}}});
const music={isAuthorized:true,bitrate:256,storefrontId:'us',api:{music:async(path,query)=>{
  requests.push({path,query});let response;
  if(path.endsWith('/search'))response={results:{artists:{data:[artist(100),artist(101)]}}};
  else if(/\/songs\/[^/]+\/catalog$/.test(path)||/\/songs\/\d+$/.test(path))response={data:[song(123)]};
  else if(/\/artists\/\d+$/.test(path))response={data:[{...artist(path.split('/').at(-1)),views:{
    'top-songs':{data:[song(123),song(124)]},'latest-release':{data:[album(456)]}}}]};
  else if(path.includes('/view/'))response={data:[album(456),album(457)],next:query.offset?null:path+'?offset=24'};
  else if(/\/albums\/\d+\/tracks$/.test(path))response={data:[song(125)],next:null};
  else if(/\/albums\/\d+$/.test(path))response={data:[album(Number(path.split('/').at(-1)))]};
  else throw Error('Unexpected path '+path);
  return {data:response};
}},setQueue:async value=>transport.push(value),play:async()=>transport.push('play'),pause:async()=>transport.push('pause')};
const context=vm.createContext({location:{origin:'https://music.apple.com'},
  window:{MusicKit:{getInstance:()=>music,PlaybackBitrate:{HIGH:256}}},navigator:{},
  document:{querySelectorAll:()=>[],querySelector:()=>null},URL});
vm.runInContext(fs.readFileSync('src/apple_web_host/page.js','utf8'),context);
const call=(method,params={})=>context.emberboxAppleCommand({method,params});
(async()=>{
  let result=await call('artist',{songId:'123',name:'Wrong namesake'});
  assert.equal(requests[0].path,'/v1/catalog/us/songs/123');
  assert.equal(result.artist.id,'100');assert.equal(result.artist.name,'Emberbox Sessions 100');
  assert.equal(result.artist.image,'https://example.invalid/800x800.jpg');
  assert.equal(result.sections[1].items[0].uri,'apple:songs:123');
  assert(!JSON.stringify(result).includes('NEVER_EXPORT'));
  collaboration=true;
  result=await call('artist',{songId:'123'});assert.equal(result.choices.length,2);assert.equal(result.artist,undefined);
  assert.equal((await call('artist',{id:result.choices[1].id})).artist.id,'101');
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
  await call('artistSection',{id:'100',section:'compilations'});
  assert.equal(requests.at(-1).path,'/v1/catalog/us/artists/100/view/compilation-albums');
  result=await call('release',{id:'456'});assert.equal(result.release.trackCount,3);
  assert.equal(result.items.length,2);assert.equal(result.items[1].playable,false);assert.equal(result.next,100);
  result=await call('release',{id:'456',offset:100});assert.equal(result.items[0].id,'125');assert.equal(result.next,null);
  result=await call('artist',{songId:'i.library'});assert.equal(result.artist.id,'100');
  assert(requests.some(r=>r.path==='/v1/me/library/songs/i.library/catalog'));
  for(const id of ['../account','https://evil.invalid/','123?token=secret']) {
    await assert.rejects(call('artist',{id}));await assert.rejects(call('release',{id}));
  }
  await assert.rejects(call('artistSection',{id:'100',section:'account'}));
  assert.deepEqual(transport,[],'Browsing must never change playback');
  music.isAuthorized=false;await assert.rejects(call('artist',{id:'100'}),/Sign in/);
  console.log('PASS exact artists, collaboration choices, catalog releases/notes, paging, availability and unchanged transport');
})().catch(error=>{console.error(error);process.exitCode=1;});
