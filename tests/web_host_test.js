/* Host navigation and adapter-version contracts; no accounts or network. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),vm=require('node:vm');
const fixture=fs.mkdtempSync(path.join(os.tmpdir(),'emberbox-web-host-'));
const folder=path.resolve('src/apple_web_host');
function host(yandex){
  const profile=path.join(fixture,yandex?'yandex':'apple');
  const app={getPath:()=>profile,setPath(){},setName(){},setDesktopName(){},enableSandbox(){},
    commandLine:{appendSwitch(){}},whenReady:()=>new Promise(()=>{}),on(){}};
  const context=vm.createContext({require:name=>name==='electron'?{app}:require(name),__dirname:folder,
    process:{env:{EMBERBOX_APPLE_PROFILE:profile,EMBERBOX_WEB_SERVICE:yandex?'yandex':'apple'},versions:process.versions,on(){}},
    URL,setTimeout,clearTimeout,console});
  vm.runInContext(fs.readFileSync(path.join(folder,'main.cjs'),'utf8')+'\nglobalThis.api={command,yandexRoute};',context);
  return context.api;
}
(async()=>{
  const yandex=host(true);
  for(const route of ['/','/collection/playlists','/playlists/1234-abcd','/users/public-id/playlists/3','/search?text=Evening'])assert.equal(yandex.yandexRoute(route),route);
  for(const route of ['https://evil.invalid/playlists/123','//evil.invalid/','/account','/users/../account','/playlists/../account','/playlists/123?token=secret'])assert.equal(yandex.yandexRoute(route),'');
  const loaded=[],responses=[{__emberboxNavigate:'/collection/playlists'},{items:[{kind:'playlist',id:'/playlists/123'}]}];
  const win={webContents:{getURL:()=> 'https://music.yandex.ru/',executeJavaScript:async()=>responses.shift()},
    loadURL:async url=>loaded.push(url),isVisible:()=>false};
  const result=await yandex.command(win,{method:'browse',params:{category:'collection'}});
  assert.equal(loaded[0],'https://music.yandex.ru/collection/playlists');assert.equal(result.items[0].kind,'playlist');
  responses.push({__emberboxNavigate:'https://evil.invalid/'});
  await assert.rejects(yandex.command(win,{method:'browse'}),/ADAPTER_UNAVAILABLE/);
  assert.equal(loaded.length,1);
  responses.push({__emberboxNavigate:'/collection/playlists'},{__emberboxNavigate:'/collection/playlists'});
  await assert.rejects(yandex.command(win,{method:'browse'}),/ADAPTER_UNAVAILABLE/);
  responses.push({ready:true,authorized:true,capabilities:{store:true}});
  assert.equal((await yandex.command(win,{method:'status'})).integrationVersion,5);
  win.webContents.getURL=()=> 'https://passport.yandex.ru/';
  assert.equal((await yandex.command(win,{method:'status'})).integrationVersion,5);
  const apple=host(false);win.webContents.getURL=()=> 'https://music.apple.com/us/new';
  responses.push({ready:true,authorized:true});
  assert.equal((await apple.command(win,{method:'status'})).integrationVersion,6);
  responses.push({ready:true,id:'123'});win.emberboxQuality={snapshot:id=>({codec:'aac',track:id,evidence:'decoder'})};
  assert.equal((await apple.command(win,{method:'status'})).audioQuality.track,'123');
  console.log('PASS bounded official-site navigation, adapter update version and decoder quality');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>fs.rmSync(fixture,{recursive:true,force:true}));
