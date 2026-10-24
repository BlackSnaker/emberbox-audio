// Background Apple Music playback using an installed Electron/Chromium runtime.
// No code or user data from the application providing that runtime is loaded.
'use strict';
const {app, BrowserWindow, session, components} = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const net = require('node:net');
const {attach:attachMediaQuality}=require(path.join(__dirname,'media_quality.cjs'));
const yandex = process.env.EMBERBOX_WEB_SERVICE === 'yandex';
const service = yandex ? {title:'Yandex Music',origin:'https://music.yandex.ru/',
  url:'https://music.yandex.ru/',command:'emberboxYandexCommand',page:'yandex.js',error:'YANDEX_REQUEST_FAILED'} :
  {title:'Apple Music',origin:'https://music.apple.com/',url:'https://music.apple.com/us/new',
   command:'emberboxAppleCommand',page:'page.js',error:'APPLE_REQUEST_FAILED'};
const methods = ['status','browse','tracks','search','play','transport','seek','artist','artistSection','release',...(yandex?['wave','feedback']:[])];
const pageCommand = fs.readFileSync(path.join(__dirname,service.page),'utf8');
let enabled = false;
const profile = process.env.EMBERBOX_APPLE_PROFILE;
if (!profile) throw new Error('An independent EMBERBOX_APPLE_PROFILE is required.');
fs.mkdirSync(profile, {recursive:true, mode:0o700});
// The launcher also passes --user-data-dir before native browser startup.
if (app.getPath('userData') !== profile) app.setPath('userData', profile);
app.setName('Emberbox Audio');
if(typeof app.setDesktopName==='function')app.setDesktopName('emberbox-audio-player.desktop');
app.enableSandbox();
const cdm = process.env.EMBERBOX_WIDEVINE;
if (cdm) app.commandLine.appendSwitch('widevine-cdm-path', cdm);
const version = process.env.EMBERBOX_WIDEVINE_VERSION;
if (version) app.commandLine.appendSwitch('widevine-cdm-version', version);
const statusPath = process.env.EMBERBOX_APPLE_STATUS;
const state = {engine:'Electron', chromium:process.versions.chrome, electron:process.versions.electron,
  loaded:false, audible:false, everAudible:false, diagnostics:[]};
function record(changes) {
  Object.assign(state, changes);
  if (statusPath) {
    fs.mkdirSync(path.dirname(statusPath), {recursive:true, mode:0o700});
    fs.writeFileSync(statusPath+'.tmp', JSON.stringify(state), {mode:0o600});
    fs.renameSync(statusPath+'.tmp',statusPath);
  }
}
function appleHost(url) {
  try {const host=new URL(url).hostname;
    return (yandex?['yandex.ru','yandex.com','yandex.net','yastatic.net','yastatic-net.ru']:['apple.com','applemusic.com','cdn-apple.com','mzstatic.com']).some(root=>host===root||host.endsWith('.'+root))?host:'other';
  }catch{return 'other';}
}
function diagnostic(kind, url='', code) {
  const item={kind,host:appleHost(url)};
  if (Number.isInteger(code)) item.code=code;
  if(JSON.stringify(state.diagnostics.at(-1))!==JSON.stringify(item))
    record({diagnostics:[...state.diagnostics,item].slice(-24)});
}
function consoleDiagnostic(message, source) {
  // Strict categories only: raw console messages may contain account data.
  if (typeof message!=='string') return;
  if(message.includes('CORS policy')) {
    const target=message.match(/https?:\/\/[^\s'"<>]+/);
    const reason=message.includes('more-private address space')?'cors-private-network':
      message.includes('preflight')?'cors-preflight':
      message.includes('No \'Access-Control-Allow-Origin\'')?'cors-missing-allow-origin':
      message.includes('Access-Control-Allow-Credentials')?'cors-credentials':
      message.includes('Access-Control-Allow-Headers')?'cors-headers':'cors-rejected';
    diagnostic(reason,target?target[0]:source);
  } else {
    const status=message.match(/status of ([45]\d\d)\b/);
    if(status) diagnostic('http-error',source,Number(status[1]));
  }
}
function makeWindow(show=true) {
  const win = new BrowserWindow({width:1060,height:760,show,
    title:'Emberbox Audio · '+service.title, backgroundColor:'#282828',
    autoHideMenuBar:true,
    webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,
      allowRunningInsecureContent:false,webviewTag:false,safeDialogs:true,backgroundThrottling:false}});
  if(typeof win.setMenu==='function')win.setMenu(null);
  win.emberboxQuality=attachMediaQuality(win.webContents);
  win.on('page-title-updated',event=>event.preventDefault());
  if (process.env.EMBERBOX_APPLE_SOCKET) {
    win.on('close',event=>{if(!app.isQuitting){event.preventDefault();win.hide();}});
  }
  win.webContents.on('did-finish-load',()=>record({loaded:true}));
  win.webContents.on('audio-state-changed',(_event, audible)=>record({audible,everAudible:state.everAudible||audible}));
  win.webContents.on('render-process-gone',(_event,details)=>record({rendererExitCode:details.exitCode}));
  win.webContents.on('console-message',(...args)=>{
    const details=args[1];
    if(details&&typeof details==='object') consoleDiagnostic(details.message,details.sourceId);
    else consoleDiagnostic(args[2],args[4]);
  });
  win.webContents.on('did-fail-load',(_event,code,_description,url,isMain)=>{
    if(isMain&&code!==-3) diagnostic('page-load-failed',url,code);
  });
  win.webContents.setWindowOpenHandler(({url})=>{
    try {const u=new URL(url);if(u.protocol==='https:'&&(yandex?['yandex.ru','yandex.com'].some(root=>u.hostname===root||u.hostname.endsWith('.'+root)):(u.hostname==='apple.com'||u.hostname.endsWith('.apple.com'))))
      return {action:'allow',overrideBrowserWindowOptions:{autoHideMenuBar:true,
        webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true}}};
    } catch {}
    return {action:'deny'};
  });
  return win;
}
function yandexRoute(route) {
  if(typeof route!=='string'||route.length>2500)return '';
  try {
    const url=new URL(route,service.origin);
    if(url.origin!==new URL(service.origin).origin||url.hash)return '';
    const page=url.pathname;
    if((page==='/'||page==='/collection'||page==='/collection/playlists')&&!url.search)return page;
    if(page==='/search'&&[...url.searchParams.keys()].every(key=>key==='text')&&url.searchParams.get('text')?.length<=200)return page+url.search;
    if(!url.search&&(/^\/playlists\/[a-zA-Z0-9-]{1,100}$/.test(page)||/^\/users\/[\w.@-]{1,100}\/playlists\/\d{1,20}$/.test(page)))return page;
  }catch{}
  return '';
}
async function command(win, request, navigations=0) {
  const params=request.params||{};
  if(request.method==='show'){win.show();win.focus();record({windowVisible:true});return {shown:true};}
  if(request.method==='hide'){win.hide();record({windowVisible:false});return {hidden:true};}
  if(request.method==='enable') {
    enabled=params.enabled===true;
    if(win.webContents.getURL().startsWith(service.origin)) {
      await win.webContents.executeJavaScript('window.__emberboxPlaybackAllowed='+JSON.stringify(enabled));
      if(!enabled) await command(win,{method:'transport',params:{action:'pause'}}).catch(()=>{});
    }
    return {enabled};
  }
  if(!methods.includes(request.method)) throw Error('UNSUPPORTED');
  if(!win.webContents.getURL().startsWith(service.origin)) {
    if(yandex&&request.method!=='status')throw Error('SIGN_IN_REQUIRED');
    return {ready:false,authorized:false,integrationVersion:yandex?5:6};
  }
  const reasons=['CONTENT_EQUIVALENT','CONTENT_UNAVAILABLE','CONTENT_UNSUPPORTED','DEVICE_LIMIT','GEO_BLOCK',
    'INVALID_ARGUMENTS','MEDIA_LICENSE','MEDIA_KEY','MEDIA_PLAYBACK','NETWORK_ERROR','SUBSCRIPTION_ERROR','TypeError','ReferenceError','Error',
    'TOKEN_EXPIRED','UNAUTHORIZED_ERROR','UNSUPPORTED_ERROR','USER_INTERACTION_REQUIRED','WIDEVINE_CDM_EXPIRED',
    'SIGN_IN_REQUIRED','NOT_READY','NOT_FOUND','REGION_UNAVAILABLE','SUBSCRIPTION_REQUIRED','ADAPTER_UNAVAILABLE','YANDEX_REQUEST_FAILED'];
  const source='(async()=>{window.__emberboxPlaybackAllowed='+JSON.stringify(enabled)+';'+pageCommand+
    ';try{return await '+service.command+'('+JSON.stringify(request)+');}catch(e){'+
    (yandex?'if(e.emberboxRoute)return {__emberboxNavigate:e.emberboxRoute};':'')+
    'const code='+ (yandex?'String(e.message||e.name)': 'String(e.message||"").includes("Sign in to Apple Music")?"SIGN_IN_REQUIRED":String(e.message||"").includes("MusicKit is not ready")?"NOT_READY":e.errorCode||e.reason||e.name')+';const hints=["is not a function","Invalid queue","No playable","storefront","not writable","undefined","not supported","user interaction"];'+
    'return {__emberboxError:'+JSON.stringify(reasons)+'.includes(code)?code:'+JSON.stringify(service.error)+','+
    'stage:["storefront","queue","start"].includes(e.emberboxStage)?e.emberboxStage:"other",'+
    'hint:hints.find(h=>String(e.message||"").includes(h))||"other"};}})()';
  const result=await win.webContents.executeJavaScript(source,['play','transport','wave','feedback'].includes(request.method));
  if(yandex&&result?.__emberboxNavigate) {
    const route=yandexRoute(result.__emberboxNavigate);
    if(!route||navigations>=1)throw Error('ADAPTER_UNAVAILABLE');
    await win.loadURL(new URL(route,service.origin).href);
    return command(win,request,navigations+1);
  }
  if(result?.__emberboxError){
    diagnostic((yandex?'yandex-api-':'apple-api-')+result.stage+'-'+result.hint);
    throw Error(result.__emberboxError);
  }
  if(request.method==='status')record({ready:!!result.ready,authorized:!!result.authorized,
    playing:!!result.playing,position:Number(result.position)||0,duration:Number(result.duration)||0,
    hasTrack:!!result.title,windowVisible:win.isVisible()});
  if(request.method==='status') {
    result.integrationVersion=yandex?5:7;
    result.audioQuality=win.emberboxQuality?.snapshot(String(result.id||result.title||''))||{};
    record({audioQuality:result.audioQuality,maximumQualityRequested:result.qualityPreference?.applied===true});
    if(yandex)record({capabilities:Object.fromEntries(['player','wave','navigation','metadata','store','legacy'].map(key=>[key,result.capabilities?.[key]===true]))});
  }
  return result;
}
function connectBridge(win) {
  if(!process.env.EMBERBOX_APPLE_SOCKET)return;
  const socket=net.createConnection(process.env.EMBERBOX_APPLE_SOCKET);
  let buffer='';
  socket.on('error',()=>{});
  socket.on('data',data=>{
    buffer+=data.toString('utf8');
    if(buffer.length>2000000){socket.destroy();return;}
    let end;
    while((end=buffer.indexOf('\n'))>=0) {
      const line=buffer.slice(0,end);buffer=buffer.slice(end+1);
      let request;try{request=JSON.parse(line);}catch{socket.destroy();return;}
      if(typeof request.id!=='string'||request.id.length>100)continue;
      let timer;
      const timeout=new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('TIMEOUT')),14000);});
      Promise.race([command(win,request),timeout]).then(result=>{
        if(!socket.destroyed)socket.write(JSON.stringify({id:request.id,result})+'\n');
      }).catch(error=>{
        const value=String(error.message||'');
        const allowed=['CONTENT_EQUIVALENT','CONTENT_UNAVAILABLE','CONTENT_UNSUPPORTED','DEVICE_LIMIT','GEO_BLOCK',
          'INVALID_ARGUMENTS','MEDIA_LICENSE','MEDIA_KEY','MEDIA_PLAYBACK','NETWORK_ERROR','SUBSCRIPTION_ERROR','TypeError','ReferenceError','Error',
          'TOKEN_EXPIRED','UNAUTHORIZED_ERROR','UNSUPPORTED_ERROR','USER_INTERACTION_REQUIRED','WIDEVINE_CDM_EXPIRED',
          'SIGN_IN_REQUIRED','NOT_READY','NOT_FOUND','REGION_UNAVAILABLE','SUBSCRIPTION_REQUIRED','ADAPTER_UNAVAILABLE','YANDEX_REQUEST_FAILED'];
        const code=allowed.includes(value)?value:value.includes('Sign in to Apple Music')?'SIGN_IN_REQUIRED':
          value.includes('MusicKit is not ready')?'NOT_READY':value==='TIMEOUT'?'TIMEOUT':service.error;
        if(!socket.destroyed)socket.write(JSON.stringify({id:request.id,error:code})+'\n');
      }).finally(()=>clearTimeout(timer));
    }
  });
  socket.on('close',()=>{if(!app.isQuitting)setTimeout(()=>connectBridge(win),700).unref();});
}
const PROBE = `<!doctype html><meta charset="utf-8"><title>Emberbox local EME probe</title><script>
(async()=>{const audio=document.createElement('audio');const result={
 secureContext:isSecureContext,eme:!!navigator.requestMediaKeySystemAccess,
 aac:audio.canPlayType('audio/mp4; codecs="mp4a.40.2"')};
 try{const access=await navigator.requestMediaKeySystemAccess('com.widevine.alpha',[
 {initDataTypes:['cenc'],audioCapabilities:[{contentType:'audio/mp4; codecs="mp4a.40.2"',robustness:'SW_SECURE_CRYPTO'}]},
 {initDataTypes:['cenc'],audioCapabilities:[{contentType:'audio/mp4; codecs="mp4a.40.2"'}]}]);
 result.widevine=true;result.mediaKeysCreated=!!(await access.createMediaKeys());
 }catch(e){result.widevine=false;result.error=e.name;}
 await fetch('/result',{method:'POST',body:JSON.stringify(result)});
})();</script>`;
app.whenReady().then(async()=>{
  if (typeof session.defaultSession.setProxy === 'function')
    await session.defaultSession.setProxy({mode:'system'});
  if (components && typeof components.whenReady==='function') await components.whenReady();
  const requests=session.defaultSession.webRequest;
  if(requests&&typeof requests.onErrorOccurred==='function')
    requests.onErrorOccurred({urls:yandex?['https://*.yandex.ru/*','https://*.yandex.net/*']:['https://*.apple.com/*']},details=>{
      const errors=['net::ERR_CONNECTION_CLOSED','net::ERR_CONNECTION_RESET','net::ERR_TIMED_OUT',
        'net::ERR_NAME_NOT_RESOLVED','net::ERR_CERT_AUTHORITY_INVALID','net::ERR_FAILED'];
      diagnostic(errors.includes(details.error)?details.error:'request-error',details.url);
    });
  if (process.env.EMBERBOX_APPLE_PROBE==='1') {
    const server=http.createServer((req,res)=>{
      if(req.method==='POST'&&req.url==='/result') {
        let body='';req.on('data',chunk=>{body+=chunk;if(body.length>4096)req.destroy();});
        req.on('end',()=>{try{const result=JSON.parse(body);record({capabilities:result});
          process.stdout.write(JSON.stringify(state)+'\n');res.end('ok');
          setTimeout(()=>{server.close();app.quit();},100);}catch{res.writeHead(400);res.end();}});
      } else {res.setHeader('Content-Type','text/html; charset=utf-8');res.end(PROBE);}
    });
    server.listen(0,'127.0.0.1',()=>{
      const win=makeWindow(false);win.loadURL('http://127.0.0.1:'+server.address().port);
    });
    setTimeout(()=>{record({timeout:true});process.stdout.write(JSON.stringify(state)+'\n');app.quit();},20000).unref();
  } else {
    const seconds=Number(process.env.EMBERBOX_APPLE_SMOKE_SECONDS||0);
    const win=makeWindow(!seconds && process.env.EMBERBOX_APPLE_HIDE!=='1');
    connectBridge(win);
    if(seconds) setTimeout(()=>{process.stdout.write(JSON.stringify(state)+'\n');app.quit();},seconds*1000);
    await win.loadURL(service.url);
  }
}).catch(error=>{record({startupError:error.name,
  localStack:String(error.stack).split('\n').slice(1).filter(line=>line.includes('app.asar')).slice(0,4)});
  process.stdout.write(JSON.stringify(state)+'\n');app.quit();});
app.on('window-all-closed',()=>app.quit());
app.on('before-quit',()=>{app.isQuitting=true;});
process.on('SIGTERM',()=>{app.isQuitting=true;app.quit();});
