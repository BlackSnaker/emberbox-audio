/* Official Spotify website adapter. Credentials and internal objects stay in
 * the sandboxed website. Only named music fields cross the local IPC bridge. */
async function emberboxSpotifyCommand(request) {
 if(location.origin!=='https://open.spotify.com')throw Error('NOT_READY');
 const allowed=['status','browse','search','tracks','play','transport','seek','artist','artistSection','release'];
 if(!allowed.includes(request.method))throw Error('INVALID_ARGUMENTS');
 const p=request.params||{},finite=n=>Number.isFinite(Number(n))?Math.max(0,Number(n)):0;
 const clean=n=>String(n||'').trim().slice(0,300);
 const image=u=>{if(String(u).startsWith('spotify:image:'))u='https://i.scdn.co/image/'+u.split(':').pop();try{return new URL(u).protocol==='https:'?String(u):'';}catch{return '';}};
 const api=name=>(() => {
  const el = document.querySelector('main') || document.querySelector('#main');
  if (!el) return null;
  let fiber = el[Object.keys(el).find(k => k.startsWith('__reactFiber'))];
  function resolvePlayer(registry, seen = new Set()) {
    if (!registry || seen.has(registry)) return null;
    seen.add(registry);
    const key = Array.from(registry._map?.keys() || [])
      .find(k => String(k) === 'Symbol('+name+')');
    if (key) return registry.resolve(key);
    for (const parent of registry._parents || []) {
      const player = resolvePlayer(parent, seen);
      if (player) return player;
    }
    return null;
  }
  for (let depth = 0; fiber && depth < 300; depth++, fiber = fiber.return) {
    const values = [fiber.memoizedProps?.value];
    for (let context = fiber.dependencies?.firstContext; context; context = context.next)
      values.push(context.memoizedValue);
    for (const value of values) {
      if (typeof value?.getRegistry !== 'function') continue;
      const player = resolvePlayer(value.getRegistry());
      if (player) return player;
    }
  }
  return null;
})();
 const player=api('PlayerAPI');
 let ps={};try{ps=await player?.getState?.()||{};}catch{}
 const item=ps.item||ps.track||{},metadata=item.metadata||{};
 const footer=document.querySelector('[data-testid="now-playing-widget"],footer');
 const media=Array.from(document.querySelectorAll('audio,video')).find(m=>!m.paused)||document.querySelector('audio,video');
 const meta=navigator.mediaSession?.metadata;
 const link=(root,type)=>root?.querySelector('a[href^="/'+type+'/"]');
 const identifier=(value,type)=>String(value||'').match(new RegExp('(?:spotify:'+type+':|/'+type+'/)([A-Za-z0-9]{1,64})(?:$|[?#/])'))?.[1]||'';
 const uri=String(item.uri||ps.track_window?.current_track?.uri||''),id=identifier(uri,'track')||identifier(link(footer,'track')?.getAttribute('href'),'track');
 const title=clean(metadata.title||item.name||meta?.title||link(footer,'track')?.textContent);
 const artist=clean(metadata.artist_name||item.artists?.map(a=>a.name).join(', ')||meta?.artist||link(footer,'artist')?.textContent);
 const album=clean(metadata.album_title||item.album?.name||meta?.album);
 const artists=Array.from(footer?.querySelectorAll('a[href*="/artist/"]')||[]).map(a=>({id:identifier(a.getAttribute('href'),'artist'),name:clean(a.textContent)})).filter(a=>a.id).slice(0,12);
 for(const a of [...(Array.isArray(item.artists)?item.artists:[]),...Array.from({length:12},(_,i)=>({uri:metadata['artist_uri:'+i]||(i===0?metadata.artist_uri:''),name:metadata['artist_name:'+i]||(i===0?metadata.artist_name:'')}))]){
  const ident=identifier(a.uri||('spotify:artist:'+String(a.id||'')),'artist');
  if(ident&&!artists.some(v=>v.id===ident))artists.push({id:ident,name:clean(a.name)});
 }
 const known=window.__emberboxSpotifyMusic?.get(id)||{};
 const albumId=identifier(metadata.album_uri,'album')||String(item.album?.id||'')||identifier(item.album?.uri,'album')||identifier(link(footer,'album')?.getAttribute('href'),'album')||known.albumId||'';
 const clock=value=>{const a=String(value||'').trim().split(':').map(Number);return a.length>1&&a.every(Number.isFinite)?a.reduce((n,v)=>n*60+v,0):finite(value);};
 const basePosition=finite(ps.positionAsOfTimestamp===undefined?media?.currentTime:ps.positionAsOfTimestamp/1000)||clock(document.querySelector('[data-testid="playback-position"]')?.textContent);
 const duration=finite((item.duration?.milliseconds??metadata.duration??metadata.duration_ms??ps.duration)/1000)||finite(media?.duration)||clock(document.querySelector('[data-testid="playback-duration"]')?.textContent);
 const stampMs=Number(ps.timestamp);
 const elapsed=ps.isPaused===false&&Number.isFinite(stampMs)&&Date.now()>=stampMs&&Date.now()-stampMs<86400000?(Date.now()-stampMs)/1000:0;
 const position=Math.min(duration||86400,basePosition+elapsed);
 const authorized=!!document.querySelector('[data-testid="user-widget-link"],[data-testid="user-widget-avatar"],button[data-testid="user-widget-button"]');
 const playing=typeof ps.isPaused==='boolean'?!ps.isPaused:media?!media.paused&&!media.ended:navigator.mediaSession?.playbackState==='playing';
 const control=id=>document.querySelector('[data-testid="'+id+'"]');
 const enabled=window.__emberboxPlaybackAllowed===true;
 const status={ready:document.readyState==='complete'&&!!document.querySelector('main'),authorized,playing:!!playing,
  id,uri:id?'spotify:track:'+id:'',title,artist,album,albumId,artists,position,duration,
  image:image(meta?.artwork?.[0]?.src||metadata.image_xlarge_url||metadata.image_url||footer?.querySelector('img')?.src),
  canNext:!!control('control-button-skip-forward')&&!control('control-button-skip-forward').disabled,
  canPrevious:!!control('control-button-skip-back')&&!control('control-button-skip-back').disabled,
  canSeek:!!id&&duration>0,ended:!!media?.ended,capabilities:{player:!!player,metadata:!!(title||meta)},emberFlow:false,emberBeatSync:false};
 if(request.method==='status')return status;
 if(!authorized)throw Error('SIGN_IN_REQUIRED');
 const wait=async work=>{for(let n=0;n<70;n++){const v=await work();if(v)return v;await new Promise(resolve=>setTimeout(resolve,150));}throw Error('NOT_READY');};
 function routeValid(route){return typeof route==='string'&&route.length<1200&&/^\/(?:$|collection\/(tracks|albums|playlists)$|(track|album|playlist)\/[A-Za-z0-9]{1,64}$|artist\/[A-Za-z0-9]{1,64}(\/discography\/(all|album|single|compilation))?$|search\/[^/]{1,800}$)/.test(route);}
 async function navigate(route){
  if(!routeValid(route))throw Error('INVALID_ARGUMENTS');
  if(location.pathname===route)return;
  const moved=(() => {
  const path=route;
  if(location.pathname===path)return true;
  const link=Array.from(document.querySelectorAll('a[href]')).find(a=>a.getAttribute('href')===path);
  if(link){link.click();return true;}
  const root=document.querySelector('main');let f=root?.[Object.keys(root).find(k=>k.startsWith('__reactFiber'))];
  for(let n=0;f&&n<180;n++,f=f.return){
    const values=[f.memoizedProps?.value];
    for(let d=f.dependencies?.firstContext,i=0;d&&i<24;i++,d=d.next)values.push(d.memoizedValue);
    for(const value of values){const nav=value?.navigator;
      if(typeof nav?.push==='function'&&typeof nav?.createHref==='function'){nav.push(path);return true;}}
  }
  return false;
})();
  if(!moved){const e=Error('NOT_READY');e.emberboxRoute=route;throw e;}
  await wait(()=>location.pathname===route);await new Promise(resolve=>setTimeout(resolve,250));
 }
 const pathFor=uri=>{if(!/^spotify:(track|album|playlist):[A-Za-z0-9]{1,64}$/.test(String(uri)))throw Error('INVALID_ARGUMENTS');return '/'+uri.split(':').slice(1).join('/');};
 if(request.method==='play'){
  if(!enabled)return {skipped:true};const uri=String(p.uri||'');const route=pathFor(uri);
  if(player?.play){await player.play({uri},{featureIdentifier:'emberbox-audio'});return {ok:true};}
  await navigate(route);
  const play=await wait(()=>document.querySelector('main button[data-testid="play-button"],main button[data-testid="play-pause-button"]'));
  if(play.disabled)throw Error('PREMIUM_REQUIRED');play.click();return {ok:true};
 }
 if(request.method==='transport'){
  if(!['toggle','play','resume','pause','next','previous'].includes(p.action))throw Error('INVALID_ARGUMENTS');
  if(p.action!=='pause'&&!enabled)return {skipped:true};
  if(p.action==='pause'&&!playing||['play','resume'].includes(p.action)&&playing)return {ok:true};
  const method={next:'skipToNext',previous:'skipToPrevious',pause:'pause',play:'resume',resume:'resume',toggle:playing?'pause':'resume'}[p.action];
  if(typeof player?.[method]==='function'){await player[method]();return {ok:true};}
  const c=control({next:'control-button-skip-forward',previous:'control-button-skip-back'}[p.action]||'control-button-playpause');
  if(!c||c.disabled)throw Error('ADAPTER_UNAVAILABLE');c.click();return {ok:true};
 }
 if(request.method==='seek'){
  if(typeof p.position!=='number'||!Number.isFinite(p.position)||p.position<0)throw Error('INVALID_ARGUMENTS');
  if(typeof player?.seekTo==='function'){
   try{await player.seekTo(Math.min(p.position,duration||p.position)*1000);return {ok:true};}
   catch(e){const message=String(e?.message||'');
    if(/premium/i.test(message))throw Error('PREMIUM_REQUIRED');
    if(/restricted|disallow|not allowed|forbidden|preview/i.test(message))throw Error('PLAYBACK_RESTRICTED');
    throw e;}
  }
  if(media&&Number.isFinite(media.duration)){media.currentTime=Math.min(p.position,media.duration);return {ok:true};}
  throw Error('ADAPTER_UNAVAILABLE');
 }
 function entityName(){
  const root=document.querySelector('main');
  const explicit=root?.querySelector('[data-testid="entityTitle"],[data-testid="artist-name"],[data-testid="artist-title"],h1,[role="heading"][aria-level="1"]');
  if(explicit?.textContent?.trim())return clean(explicit.textContent);
  // Current web artist headers use display spans rather than h1. Read the
  // visible display heading inside the music page, never the library sidebar.
  const labels=Array.from((root?.querySelector('[data-testid="entity-header"]')||root)?.querySelectorAll('span,div,h1,h2,p')||[]).slice(0,600)
   .map(node=>({node,size:parseFloat(getComputedStyle(node).fontSize)||0}))
   .filter(v=>v.size>=30&&v.node.textContent.trim()&&v.node.textContent.trim().length<=300)
   .sort((a,b)=>b.size-a.size||a.node.textContent.trim().length-b.node.textContent.trim().length);
  return clean(labels[0]?.node.textContent);
 }
 function entityImage(root){
  const direct=root?.querySelector('[data-testid="artist-image"] img,[data-testid="entity-image"] img,[data-testid="entityImage"] img,[data-testid="entity-header"] img');
  if(direct?.src)return image(direct.src);
  const header=root?.querySelector('[data-testid="entity-header"]');
  for(const node of [header,root,...Array.from(root?.querySelectorAll('div')||[]).slice(0,100)]){
   if(!node)continue;
   const background=[getComputedStyle(node).backgroundImage,getComputedStyle(node,'::before').backgroundImage,node.style?.getPropertyValue('--background-image')].join(' ');
   const url=background.match(/url\(["']?(https:[^"')]+)["']?\)/)?.[1];
   if(url)return image(url);
  }
  return '';
 }
 const offset=Number(p.offset||0);if(!Number.isInteger(offset)||offset<0||offset>50000)throw Error('INVALID_ARGUMENTS');
 function normalize(values){return (values||[]).map(v=>({...v,id:v.id||String(v.uri||'').split(':').pop(),kind:v.kind||'track',image:image(v.image)}));}
 function cards(root=document.querySelector('main')){
  const seen=new Set(),out=[];
  for(const a of root?.querySelectorAll('a[href]')||[]){
   const m=a.getAttribute('href')?.match(/^\/(playlist|album)\/([A-Za-z0-9]{1,64})(?:$|\?)/);if(!m||seen.has(m[0]))continue;
   const c=a.closest('[data-encore-id="card"],[data-testid="grid-cell"],[role="listitem"]');if(!c)continue;
   const title=clean(c.querySelector('[data-encore-id="cardTitle"]')?.textContent||a.textContent);if(!title)continue;
   seen.add(m[0]);out.push({id:m[2],kind:m[1],uri:'spotify:'+m[1]+':'+m[2],href:'/'+m[1]+'/'+m[2],title,
    subtitle:clean(c.querySelector('[data-encore-id="cardSubtitle"]')?.textContent),image:image(c.querySelector('img')?.src)});
   if(out.length>=100)break;
  }return out;
 }
 async function tracks(uri){
  const route=pathFor(uri);if(!/^\/(playlist|album)\//.test(route))throw Error('INVALID_ARGUMENTS');
  await navigate(route);
  const data=await wait(()=>{const expected=uri;const value=(() => {
  const rows = Array.from(document.querySelectorAll('main [data-testid="tracklist-row"]'));
  if (!rows.length) return null;
  function fiber(el) { return el[Object.keys(el).find(k => k.startsWith('__reactFiber'))]; }
  let context = '', cache = null;
  for (let f = fiber(rows[0]), depth = 0; f && depth < 65; f = f.return, depth++) {
    const p = f.memoizedProps || {};
    if (!context && typeof p.contextUri === 'string') context = p.contextUri;
    if (p.itemsCache?.getItems) { cache = p.itemsCache; break; }
  }
  if (context && context !== expected) return null;
  const total = Number(cache?.nrValidItems || rows.length);
  let items = cache ? cache.getItems(offset, Math.min(offset+49, total - 1), {cachedOnly: true}) : [];
  if (!cache) {
    items = rows.map(row => {
      for (let f = fiber(row), n = 0; f && n < 35; f = f.return, n++) {
        if (f.memoizedProps?.item?.uri) return f.memoizedProps.item;
      }
      return null;
    });
  }
  if (cache && items.filter(Boolean).length < Math.min(total-offset, 50)) {
    cache.getItems(offset, Math.min(offset+49, total - 1));
  }
  return {
    title: entityName(),
    context, total, loaded:items.filter(Boolean).length, expected:Math.max(0,Math.min(50,total-offset)), cached:!!cache,
    tracks: items.filter(Boolean).map(t => t.track || t).filter(t => t.uri?.startsWith('spotify:track:')).map(t => ({
      uri: t.uri, title: t.name || '',
      artist: (t.artists || []).map(a => a.name).join(', '),
      album: t.album?.name || '',albumId:String(t.album?.id||'')||identifier(t.album?.uri,'album'),
      image: t.album?.images?.find(i => i.label === 'small')?.url || t.album?.images?.[0]?.url || '',
      duration_ms: t.duration?.milliseconds || 0,
      playable: t.isPlayable !== false
    }))
  };
})();return value&&value.tracks?.length&&(!value.cached||value.loaded>=value.expected)?value:null;});
  const values=normalize(data.tracks);
  const music=window.__emberboxSpotifyMusic||(window.__emberboxSpotifyMusic=new Map());
  for(const v of values)music.set(v.id,{albumId:v.albumId||''});
  while(music.size>2000)music.delete(music.keys().next().value);
  return {title:clean(data.title),items:values,tracks:values,total:data.total,
   next:data.cached&&offset+data.expected<data.total?offset+data.expected:null};
 }
 if(request.method==='tracks')return tracks(p.uri||'spotify:'+String(p.kind||'playlist')+':'+String(p.id||''));
 if(request.method==='browse'){
  const category=p.category||'home';if(!['home','playlists','albums','collection','dj','recent'].includes(category))throw Error('INVALID_ARGUMENTS');
  await navigate(category==='albums'?'/collection/albums':category==='playlists'||category==='collection'?'/collection/playlists':'/');
  let shelves=await wait(()=>{const existing=(() => {
  if (!document.querySelector('[data-testid="home-page"]')) return null;
  const shelves = Array.from(document.querySelectorAll('main section[data-testid="component-shelf"]'));
  return shelves.map((s, index) => ({
    title: index === 0 ? 'Миксы дня и открытия' : (s.querySelector('h2')?.innerText || ''),
    items: Array.from(s.querySelectorAll('[data-encore-id="card"]')).map(c => {
      const a = c.querySelector('a[href]');
      return {
        title: c.querySelector('[data-encore-id="cardTitle"]')?.textContent?.trim() || '',
        subtitle: c.querySelector('[data-encore-id="cardSubtitle"]')?.textContent?.trim() || '',
        href: a?.getAttribute('href') || '',
        image: c.querySelector('img')?.getAttribute('src') || ''
      };
    }).filter(c => /^\/(playlist|album)\/[A-Za-z0-9]+$/.test(c.href) && c.title)
  })).filter(s => s.items.length);
})();if(existing?.length)return existing;const values=cards();return values.length?[{title:'Spotify',items:values}]:null;});
  shelves=shelves.slice(0,30).map(s=>({title:clean(s.title),items:s.items.map(v=>({...v,id:v.id||v.href.split('/').pop(),kind:v.kind||(v.href.startsWith('/album/')?'album':'playlist'),uri:v.uri||'spotify:'+v.href.slice(1).replace('/',':'),image:image(v.image)})).slice(0,100)}));
  return {shelves,items:shelves.flatMap(s=>s.items).slice(0,150),next:null};
 }
 if(request.method==='search'){
  const term=String(p.term||'').trim();if(!term||term.length>200)throw Error('INVALID_ARGUMENTS');
  await navigate('/search/'+encodeURIComponent(term));
  let fallback=[];
  for(let attempt=0;attempt<35;attempt++){
   const songs=[],seen=new Set();
   // Search shelves have h2 headings, not the h1 required by artist pages.
   const rows=Array.from(document.querySelectorAll('main [data-testid="tracklist-row"]'));
   const linked=Array.from(document.querySelectorAll('main a[href*="/track/"]')).map(a=>a.closest('[role="row"],[data-encore-id="card"],[role="listitem"]')||a.parentElement);
   for(const row of [...rows,...linked]){
    const a=row.querySelector('a[href*="/track/"]'),ident=identifier(a?.getAttribute('href'),'track');
    if(!ident||seen.has(ident))continue;seen.add(ident);
    const stamp=Array.from(row.querySelectorAll('[data-encore-id="text"]')).map(v=>v.textContent.trim()).find(v=>/^\d+:\d\d$/.test(v));
    songs.push({id:ident,uri:'spotify:track:'+ident,kind:'track',title:clean(a.textContent),
     artist:clean(Array.from(row.querySelectorAll('a[href*="/artist/"]')).map(v=>v.textContent.trim()).join(', ')),
     album:clean(row.querySelector('a[href*="/album/"]')?.textContent),image:image(row.querySelector('img')?.src),duration_ms:clock(stamp)*1000});
   }
   fallback=cards();if(songs.length)return {items:songs.concat(fallback).slice(0,100)};
   await new Promise(resolve=>setTimeout(resolve,150));
  }
  return {items:fallback};
 }

 let artistId=String(p.id||'');
 if(artistId&&!/^[A-Za-z0-9]{1,64}$/.test(artistId))throw Error('INVALID_ARGUMENTS');
 if(request.method==='release'){
  if(!artistId){const ref=(() => {
  const uri=String(p.songUri||''),current=true;
  const id=uri.match(/(?:spotify:track:|\/track\/)([A-Za-z0-9]{1,64})(?:$|[?/#])/)?.[1];
  if(!id)return null;
  const row=Array.from(document.querySelectorAll('main [data-testid="tracklist-row"]'))
    .find(row=>row.querySelector('a[href="/track/'+id+'"]'));
  const footer=current?document.querySelector('footer, [data-testid="now-playing-widget"]'):null;
  const currentId=footer?.querySelector('a[href*="/track/"]')?.getAttribute('href')?.match(/^\/track\/([A-Za-z0-9]{1,64})(?:$|\?)/)?.[1];
  const root=row||(footer&&currentId===id?footer:null);
  const href=root?.querySelector('a[href*="/album/"]')?.getAttribute('href')||'';
  const album=href.match(/^\/album\/([A-Za-z0-9]{1,64})(?:$|\?)/)?.[1];
  return album?{id:album}:null;
})();artistId=ref?.id||'';
   const recording=identifier(p.songUri,'track');
   if(!artistId&&recording){
    artistId=window.__emberboxSpotifyMusic?.get(recording)?.albumId||'';
    if(!artistId){
     await navigate('/track/'+recording);
     artistId=await wait(()=>identifier(document.querySelector('main [data-testid="entity-header"] a[href*="/album/"]')?.getAttribute('href'),'album'));
    }
   }
  }
  if(!/^[A-Za-z0-9]{1,64}$/.test(artistId))throw Error('NOT_READY');
  const data=await tracks('spotify:album:'+artistId),info=(() => {
  const root=document.querySelector('main');if(!root)return null;
  const name=entityName();if(!name)return null;
  const seen=new Set(),releases=[];
  for(const link of root.querySelectorAll('a[href*="/album/"]')){
    const id=link.getAttribute('href')?.match(/^\/album\/([A-Za-z0-9]{1,64})$/)?.[1];
    const card=link.closest('[data-encore-id="card"]');if(!id||!card||seen.has(id))continue;seen.add(id);
    releases.push({id,kind:'album',uri:'spotify:album:'+id,href:'/album/'+id,
      title:card.querySelector('[data-encore-id="cardTitle"]')?.textContent.trim()||link.textContent.trim(),
      subtitle:card.querySelector('[data-encore-id="cardSubtitle"]')?.textContent.trim()||'',image:card.querySelector('img')?.src||''});
    if(releases.length>=100)break;
  }
  const songs=[];
  for(const row of root.querySelectorAll('[data-testid="tracklist-row"]')){
    const link=row.querySelector('a[href*="/track/"]');
    const id=link?.getAttribute('href')?.match(/^\/track\/([A-Za-z0-9]{1,64})$/)?.[1];if(!id)continue;
    const parts=(Array.from(row.querySelectorAll('[data-encore-id="text"]')).map(a=>a.textContent.trim()).find(t=>/^\d+:\d\d$/.test(t))||'').split(':').map(Number);
    songs.push({id,uri:'spotify:track:'+id,kind:'track',title:link.textContent.trim(),
      artist:Array.from(row.querySelectorAll('a[href*="/artist/"]')).map(a=>a.textContent.trim()).join(', '),
      image:row.querySelector('img')?.src||'',duration_ms:parts.length===2?(parts[0]*60+parts[1])*1000:0});
    if(songs.length>=50)break;
  }
  const image=entityImage(root);
  const bio=root.querySelector('[data-testid="artist-about-description"], [data-testid="artist-biography"], [data-testid="artist-about"] p')?.textContent.trim().slice(0,14000)||'';
  const links=Array.from(root.querySelectorAll('a[href]')).map(a=>a.getAttribute('href'))
    .filter(p=>/^\/artist\/[A-Za-z0-9]{1,64}\/discography\/(all|album|single|compilation)$/.test(p));
  return {name,image,bio,releases,songs,links};
})();
  return {...data,release:{id:artistId,kind:'album',uri:'spotify:album:'+artistId,title:data.title,image:image(info?.image),description:clean(info?.bio)}};
 }
 if(!artistId){const refs=(() => {
  const uri=String(p.songUri||''),current=true,seen=new Set(),result=[];
  const id=uri.match(/(?:spotify:track:|\/track\/)([A-Za-z0-9]+)/)?.[1];
  const row=id?Array.from(document.querySelectorAll('main [data-testid="tracklist-row"]'))
    .find(row=>row.querySelector('a[href="/track/'+id+'"]')):null;
  const footer=current?document.querySelector('footer, [data-testid="now-playing-widget"]'):null;
  const currentId=footer?.querySelector('a[href*="/track/"]')?.getAttribute('href')?.match(/^\/track\/([A-Za-z0-9]+)/)?.[1];
  const root=row||(footer&&(!id||id===currentId)?footer:null);
  for(const link of root?.querySelectorAll('a[href*="/artist/"]')||[]){
    const id=link.getAttribute('href')?.match(/^\/artist\/([A-Za-z0-9]{1,64})$/)?.[1];
    const name=link.textContent.trim();if(!id||!name||seen.has(id))continue;seen.add(id);result.push({id,name});}
  return result;
})();if(refs.length===1)artistId=refs[0].id;else if(refs.length)return {choices:refs};
  else {await navigate('/search/'+encodeURIComponent(String(p.name||'').slice(0,200)));return {choices:(() => {
  const seen=new Set(),result=[];
  for(const link of document.querySelectorAll('main a[href*="/artist/"]')){
    const id=link.getAttribute('href')?.match(/^\/artist\/([A-Za-z0-9]{1,64})$/)?.[1];
    const card=link.closest('[data-encore-id="card"]');if(!id||!card||seen.has(id))continue;
    const name=card.querySelector('[data-encore-id="cardTitle"]')?.textContent.trim()||link.textContent.trim();
    if(!name)continue;seen.add(id);result.push({id,name,image:card.querySelector('img')?.src||''});
  }
  return result.slice(0,20);
})()};}}
 await navigate('/artist/'+artistId);
 if(request.method==='artistSection'){
  const suffix={discography:'all',albums:'album',singles:'single',compilations:'compilation'}[p.section];
  if(suffix)await navigate('/artist/'+artistId+'/discography/'+suffix);
 }
 const info=await wait(()=>(() => {
  const root=document.querySelector('main');if(!root)return null;
  const name=entityName();if(!name)return null;
  const seen=new Set(),releases=[];
  for(const link of root.querySelectorAll('a[href*="/album/"]')){
    const id=link.getAttribute('href')?.match(/^\/album\/([A-Za-z0-9]{1,64})$/)?.[1];
    const card=link.closest('[data-encore-id="card"]');if(!id||!card||seen.has(id))continue;seen.add(id);
    releases.push({id,kind:'album',uri:'spotify:album:'+id,href:'/album/'+id,
      title:card.querySelector('[data-encore-id="cardTitle"]')?.textContent.trim()||link.textContent.trim(),
      subtitle:card.querySelector('[data-encore-id="cardSubtitle"]')?.textContent.trim()||'',image:card.querySelector('img')?.src||''});
    if(releases.length>=100)break;
  }
  const songs=[];
  for(const row of root.querySelectorAll('[data-testid="tracklist-row"]')){
    const link=row.querySelector('a[href*="/track/"]');
    const id=link?.getAttribute('href')?.match(/^\/track\/([A-Za-z0-9]{1,64})$/)?.[1];if(!id)continue;
    const parts=(Array.from(row.querySelectorAll('[data-encore-id="text"]')).map(a=>a.textContent.trim()).find(t=>/^\d+:\d\d$/.test(t))||'').split(':').map(Number);
    songs.push({id,uri:'spotify:track:'+id,kind:'track',title:link.textContent.trim(),
      artist:Array.from(row.querySelectorAll('a[href*="/artist/"]')).map(a=>a.textContent.trim()).join(', '),
      image:row.querySelector('img')?.src||'',duration_ms:parts.length===2?(parts[0]*60+parts[1])*1000:0});
    if(songs.length>=50)break;
  }
  const image=entityImage(root);
  const bio=root.querySelector('[data-testid="artist-about-description"], [data-testid="artist-biography"], [data-testid="artist-about"] p')?.textContent.trim().slice(0,14000)||'';
  const links=Array.from(root.querySelectorAll('a[href]')).map(a=>a.getAttribute('href'))
    .filter(p=>/^\/artist\/[A-Za-z0-9]{1,64}\/discography\/(all|album|single|compilation)$/.test(p));
  return releases.length||songs.length?{name,image,bio,releases,songs,links}:null;
})());
 if(request.method==='artistSection')return {items:normalize(info.releases),next:null,note:'Spotify web player'};
 return {artist:{id:artistId,name:clean(info.name),image:image(info.image),bio:String(info.bio||'').slice(0,14000),genres:[]},
  sections:[{id:'latest-release',items:normalize(info.releases).slice(0,20)},{id:'top-songs',items:normalize(info.songs)}],note:'Spotify web player'};
}
