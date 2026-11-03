/* Exact identity, idempotence, verification and website failure cases. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context=vm.createContext({setTimeout});
vm.runInContext(fs.readFileSync('src/apple_web_host/favorite_dom.js','utf8'),context);
(async()=>{
 let active=false,clicks=0,current=true;
 const button={getAttribute:key=>key==='aria-pressed'?String(active):null,click(){clicks++;active=!active;}};
 const set=(value)=>context.emberboxSetFavorite(()=>button,value,()=>current);
 assert.equal((await set(true)).confirmed,true);assert.equal(clicks,1);
 await set(true);assert.equal(clicks,1,'An existing favourite must never be toggled off');
 await set(false);assert.equal(clicks,2);assert.equal(active,false);
 current=false;await assert.rejects(set(true),/INVALID_ARGUMENTS/);assert.equal(clicks,2);
 await assert.rejects(context.emberboxSetFavorite(()=>({getAttribute:()=>null}),true,()=>true),/ADAPTER_UNAVAILABLE/);
 current=true;button.click=()=>{clicks++;current=false;};
 await assert.rejects(set(true),/FAVORITE_NOT_CONFIRMED/);

 let rating=false;const calls=[];
 const music={isAuthorized:true,api:{music:async(path,query,options)=>{
   calls.push([path,query,options]);
   if(options?.fetchOptions?.method==='POST')rating=true;
   if(options?.fetchOptions?.method==='DELETE')rating=false;
   return rating?{data:{data:[{attributes:{value:1}}]}}:{data:{errors:[{status:'404'}]}};
 }}};
 const apple=vm.createContext({window:{MusicKit:{getInstance:()=>music}},location:{origin:'https://music.apple.com'},setTimeout});
 vm.runInContext(fs.readFileSync('src/apple_web_host/page.js','utf8'),apple);
 const favorite=value=>apple.emberboxAppleCommand({method:'favorite',params:{id:'123',kind:'songs',value}});
 assert.equal((await favorite(true)).favorite,true);
 assert(calls.some(([path,q,o])=>path==='/v1/me/favorites'&&q['ids[songs]'][0]==='123'&&o.fetchOptions.method==='POST'));
 const writes=()=>calls.filter(v=>v[2]).length;
 const before=writes();await favorite(true);assert.equal(writes(),before);
 assert.equal((await favorite(false)).favorite,false);
 assert.equal(calls.find(v=>v[2]?.fetchOptions?.method==='DELETE')[0],'/v1/me/ratings/songs/123');
 await assert.rejects(apple.emberboxAppleCommand({method:'favorite',params:{id:'../account',kind:'songs',value:true}}),/INVALID_ARGUMENTS/);
 music.isAuthorized=false;await assert.rejects(favorite(true),/Sign in/);
 console.log('PASS verified, idempotent favourites and Apple account mutations; no credentials exported');
})().catch(error=>{console.error(error);process.exitCode=1;});
