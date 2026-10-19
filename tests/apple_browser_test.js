/* Fixture tests only: no browser session or Apple account is accessed. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const calls=[];
const resource={id:'i.test',type:'library-songs',attributes:{name:'Fixture song',artistName:'Artist',
  artwork:{url:'https://example.invalid/{w}x{h}.jpg'},durationInMillis:1000,playParams:{id:'i.test'}},
  privateToken:'DO_NOT_EXPORT',relationships:{anything:{credentials:'DO_NOT_EXPORT'}}};
const music={isAuthorized:true,api:{music:async(path,query)=>{calls.push([path,query]);return{data:{data:[resource],next:'/v1/me/library/songs?offset=50'}};}},
  setQueue:async(queue)=>calls.push(queue),play:async()=>calls.push('play')};
const context=vm.createContext({location:{origin:'https://music.apple.com'},window:{MusicKit:{getInstance:()=>music}},URL});
vm.runInContext(fs.readFileSync('browser/apple-music/page.js','utf8'),context);
(async()=>{
  const command=context.emberboxAppleCommand;
  const result=await command({method:'browse',params:{category:'songs'}});
  assert.equal(result.items[0].title,'Fixture song');
  assert.equal(result.next,1);
  assert(!JSON.stringify(result).includes('DO_NOT_EXPORT'));
  await command({method:'tracks',params:{kind:'library-albums',id:'l.fixture'}});
  assert.equal(calls[1][0],'/v1/me/library/albums/l.fixture/tracks');
  await command({method:'play',params:{kind:'library-songs',id:'i.test'}});
  assert.equal(calls[2].librarySong,'i.test');assert.equal(calls[3],'play');
  await assert.rejects(command({method:'play',params:{kind:'library-songs',id:'../../api'}}));
  await assert.rejects(command({method:'browse',params:{category:'account'}}));
  await assert.rejects(command({method:'executeJavaScript',params:{code:'anything'}}));
  music.isAuthorized=false;
  await assert.rejects(command({method:'status',params:{}}),/Sign in/);
  console.log('PASS Apple library routes, playback descriptors and metadata-only responses');
})().catch(error=>{console.error(error);process.exitCode=1;});
