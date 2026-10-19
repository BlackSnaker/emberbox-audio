// Background Apple Music playback using an installed Electron/Chromium runtime.
// No code or user data from the application providing that runtime is loaded.
'use strict';
const {app, BrowserWindow, session, components} = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const net = require('node:net');
const pageCommand = fs.readFileSync(path.join(__dirname,'page.js'),'utf8');
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
    return ['apple.com','applemusic.com','cdn-apple.com','mzstatic.com'].some(root=>host===root||host.endsWith('.'+root))?host:'other';
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
    title:'Emberbox Audio · Apple Music', backgroundColor:'#282828',
    autoHideMenuBar:true,
    webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,
      allowRunningInsecureContent:false,webviewTag:false,safeDialogs:true,backgroundThrottling:false}});
  if(typeof win.setMenu==='function')win.setMenu(null);
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
    try {const u=new URL(url);if(u.protocol==='https:'&&(u.hostname==='apple.com'||u.hostname.endsWith('.apple.com')))
      return {action:'allow',overrideBrowserWindowOptions:{autoHideMenuBar:true,
        webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true}}};
    } catch {}
    return {action:'deny'};
  });
  return win;
}
async function command(win, request) {
  const params=request.params||{};
  if(request.method==='show'){win.show();win.focus();record({windowVisible:true});return {shown:true};}
  if(request.method==='hide'){win.hide();record({windowVisible:false});return {hidden:true};}
  if(request.method==='enable') {
    enabled=params.enabled===true;
    if(win.webContents.getURL().startsWith('https://music.apple.com/')) {
      await win.webContents.executeJavaScript('window.__emberboxPlaybackAllowed='+JSON.stringify(enabled));
      if(!enabled) await command(win,{method:'transport',params:{action:'pause'}}).catch(()=>{});
    }
    return {enabled};
  }
  if(!['status','browse','tracks','search','play','transport','seek'].includes(request.method)) throw Error('UNSUPPORTED');
  if(!win.webContents.getURL().startsWith('https://music.apple.com/')) return {ready:false,authorized:false};
  const reasons=['CONTENT_EQUIVALENT','CONTENT_UNAVAILABLE','CONTENT_UNSUPPORTED','DEVICE_LIMIT','GEO_BLOCK',
    'INVALID_ARGUMENTS','MEDIA_LICENSE','MEDIA_KEY','MEDIA_PLAYBACK','NETWORK_ERROR','SUBSCRIPTION_ERROR','TypeError','ReferenceError','Error',
    'TOKEN_EXPIRED','UNAUTHORIZED_ERROR','UNSUPPORTED_ERROR','USER_INTERACTION_REQUIRED','WIDEVINE_CDM_EXPIRED',
    'SIGN_IN_REQUIRED','NOT_READY','NOT_FOUND'];
  const source='(async()=>{window.__emberboxPlaybackAllowed='+JSON.stringify(enabled)+';'+pageCommand+
    ';try{return await emberboxAppleCommand('+JSON.stringify(request)+');}catch(e){'+
    'const code=String(e.message||"").includes("Sign in to Apple Music")?"SIGN_IN_REQUIRED":String(e.message||"").includes("MusicKit is not ready")?"NOT_READY":e.errorCode||e.reason||e.name;const hints=["is not a function","Invalid queue","No playable","storefront","not writable","undefined","not supported","user interaction"];'+
    'return {__emberboxError:'+JSON.stringify(reasons)+'.includes(code)?code:"APPLE_REQUEST_FAILED",'+
    'stage:["storefront","queue","start"].includes(e.emberboxStage)?e.emberboxStage:"other",'+
    'hint:hints.find(h=>String(e.message||"").includes(h))||"other"};}})()';
  const result=await win.webContents.executeJavaScript(source,['play','transport'].includes(request.method));
  if(result?.__emberboxError){
    diagnostic('apple-api-'+result.stage+'-'+result.hint);
    throw Error(result.__emberboxError);
  }
  if(request.method==='status')record({ready:!!result.ready,authorized:!!result.authorized,
    playing:!!result.playing,position:Number(result.position)||0,duration:Number(result.duration)||0,
    hasTrack:!!result.title,windowVisible:win.isVisible()});
  if(request.method==='status')result.integrationVersion=2;
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
          'SIGN_IN_REQUIRED','NOT_READY','NOT_FOUND'];
        const code=allowed.includes(value)?value:value.includes('Sign in to Apple Music')?'SIGN_IN_REQUIRED':
          value.includes('MusicKit is not ready')?'NOT_READY':value==='TIMEOUT'?'TIMEOUT':'APPLE_REQUEST_FAILED';
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
    requests.onErrorOccurred({urls:['https://*.apple.com/*']},details=>{
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
    await win.loadURL('https://music.apple.com/us/new');
  }
}).catch(error=>{record({startupError:error.name,
  localStack:String(error.stack).split('\n').slice(1).filter(line=>line.includes('app.asar')).slice(0,4)});
  process.stdout.write(JSON.stringify(state)+'\n');app.quit();});
app.on('window-all-closed',()=>app.quit());
app.on('before-quit',()=>{app.isQuitting=true;});
process.on('SIGTERM',()=>{app.isQuitting=true;app.quit();});
