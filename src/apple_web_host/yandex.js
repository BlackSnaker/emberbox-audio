/* Typed metadata/control adapter for the official Yandex Music website.
 * Authentication and recommendation feedback stay in the site's own session.
 * Never return a store snapshot, requests, tokens, cookies or account details.
 */
async function emberboxYandexCommand(request) {
  if (location.origin !== 'https://music.yandex.ru') throw Error('NOT_READY');
  const allowed=['status','wave','browse','search','play','transport','seek','feedback'];
  if(!allowed.includes(request.method)) throw Error('UNSUPPORTED');
  const p=request.params||{};
  const state=window.__emberboxYandex||(window.__emberboxYandex={items:new Map()});
  const text=node=>String(node?.textContent||'').trim().slice(0,300);
  const selectors={
    PLAYERBAR_DESKTOP:'[class*="PlayerBar_root"], [class*="PlayerBarDesktop_root"]',
    VIBE_PLAYERBAR:'[class*="VibePlayerBar_root"]',
    TIMECODE_SLIDER:'[role="slider"][aria-label*="Время"], [class*="Timecode"] [role="slider"]',
    USER_PROFILE_USERNAME:'[class*="UserProfile_username"]',
    MY_VIBE_PLAY_BUTTON:'button[aria-label="Включить Мою волну"], button[aria-label="Воспроизвести Мою волну"], [class*="VibeButton"] button',
    MY_VIBE_PAUSE_BUTTON:'button[aria-label="Приостановить Мою волну"]',
    NEXT_TRACK_BUTTON:'button[aria-label="Следующий трек"], button[aria-label="Next track"]',
    PREVIOUS_TRACK_BUTTON:'button[aria-label="Предыдущий трек"], button[aria-label="Previous track"]',
    PLAY_BUTTON:'button[aria-label="Воспроизвести"], button[aria-label="Play"], button[aria-label^="Слушать"]',
    PAUSE_BUTTON:'button[aria-label="Пауза"], button[aria-label="Pause"], button[aria-label="Приостановить"]',
    LIKE_BUTTON:'button[aria-label="Нравится"], button[aria-label="Like"], button[aria-label="Добавить в коллекцию"]',
    DISLIKE_BUTTON:'button[aria-label="Не нравится"], button[aria-label="Dislike"]',
    PLAY_QUEUE_BUTTON:'button[aria-label*="Очередь"], button[aria-label*="очередь"], button[aria-label*="queue"]'
  };
  const test=(id,root=document)=>root.querySelector('[data-test-id$="'+id+'"]')||
    (selectors[id]?root.querySelector(selectors[id]):null);
  const visible=node=>node&&!node.disabled&&node.getAttribute('aria-disabled')!=='true'&&node.getClientRects().length>0;
  const button=(id,root=document)=>{const node=test(id,root);return visible(node)?node:null;};
  const wait=async work=>{for(let i=0;i<45;i++){const result=work();if(result)return result;await new Promise(resolve=>setTimeout(resolve,200));}throw Error('NOT_READY');};
  // The site's React providers expose its router and player view model.
  // Inspect only these named capabilities; never enumerate or export user data.
  function context() {
    if(state.store&&state.router&&state.engine)return;
    for(const element of Array.from(document.querySelectorAll('main,main *,body > div')).slice(0,45)) {
      const key=Object.keys(element).find(key=>key.startsWith('__reactFiber$'));
      let fiber=key&&element[key];
      for(let depth=0;fiber&&depth<100;depth++,fiber=fiber.return) {
        const value=fiber.memoizedProps?.value;
        if(value?.user&&value?.sonataState)state.store=value;
        if(value&&typeof value.togglePause==='function'&&typeof value.playContext==='function')state.engine=value;
        if(value&&typeof value.push==='function'&&typeof value.replace==='function'&&typeof value.prefetch==='function')state.router=value;
      }
    }
  }
  context();
  const view=state.store?.sonataState;
  const track=view?.entityMeta;
  const media=Array.from(document.querySelectorAll('audio,video')).find(node=>!node.paused)||document.querySelector('audio,video');
  const external=window.externalAPI;
  let extTrack=null,extProgress=null;
  try{extTrack=external?.getCurrentTrack?.();extProgress=external?.getProgress?.();}catch{}
  const meta=navigator.mediaSession?.metadata;
  const bar=test('PLAYERBAR_DESKTOP')||test('VIBE_PLAYERBAR')||document.querySelector('[class*="PlayerBar_root"]');
  const slider=test('TIMECODE_SLIDER',bar||document)||test('VIBE_PLAYERBAR_TIMECODE_SLIDER');
  const finite=value=>Number.isFinite(Number(value))?Math.max(0,Number(value)):0;
  const cover=value=>{if(typeof value!=='string')return '';value=value.replace('%%','400x400');
    if(!value.startsWith('http'))value='https://'+value.replace(/^\/\//,'');
    try{const url=new URL(value);return url.protocol==='https:'?url.href:'';}catch{return '';}};
  const rawCover=meta?.artwork?.[0]?.src||track?.coverUri||extTrack?.cover;
  const title=String(track?.title||meta?.title||extTrack?.title||text(test('TRACK_TITLE',bar||document))).slice(0,300);
  const artist=String(track?.artistsNames||meta?.artist||(extTrack?.artists||[]).map(a=>a.title||a.name).join(', ')).slice(0,300);
  const duration=finite(view?.duration??media?.duration??extProgress?.duration??slider?.getAttribute('aria-valuemax'));
  const position=finite(view?.position??media?.currentTime??extProgress?.position??slider?.getAttribute('aria-valuenow'));
  let playing=typeof view?.isPlaying==='boolean'?view.isPlaying:media?!media.paused&&!media.ended:navigator.mediaSession?.playbackState==='playing';
  try{if(external?.isPlaying)playing=!!external.isPlaying();}catch{}
  const bodyText=text(document.body); // region banners are short; do not export text.
  const region=/недоступна в вашем регионе|not available in your (country|region)/i.test(bodyText);
  const user=state.store?.user;
  const authorized=typeof user?.isAuthorized==='boolean'?user.isAuthorized:!!test('USER_PROFILE_USERNAME');
  const subscribed=typeof user?.hasPlus==='boolean'?user.hasPlus:null;
  const status={ready:document.readyState==='complete'&&!!state.store,authorized,subscribed,regionBlocked:region,
    capabilities:{player:!!state.engine,wave:!!state.engine?.playContext||!!button('MY_VIBE_PLAY_BUTTON'),
      navigation:!!state.router,metadata:!!view},
    playing:!!playing,title,artist,album:String(meta?.album||track?.mainAlbum?.title||extTrack?.album?.title||'').slice(0,300),
    id:String(track?.id||extTrack?.id||title).slice(0,300),image:cover(rawCover),duration,position,
    canNext:!!view?.canMoveForward||!!button('NEXT_TRACK_BUTTON')||!!external?.next,
    canPrevious:!!view?.canMoveBackward||!!button('PREVIOUS_TRACK_BUTTON')||!!external?.prev,
    wave:!!state.store?.sonataState?.isVibeContext||!!button('MY_VIBE_PAUSE_BUTTON')};
  if(request.method==='status')return status;
  if(region)throw Error('REGION_UNAVAILABLE');
  if(!authorized)throw Error('SIGN_IN_REQUIRED');
  async function navigate(route) {
    if(location.pathname+location.search===route)return;
    context();
    if(state.router){state.router.push(route);await wait(()=>location.pathname+location.search===route);return;}
    const link=Array.from(document.querySelectorAll('a[href]')).find(a=>a.getAttribute('href')===route);
    if(link){link.click();await wait(()=>location.pathname+location.search===route);return;}
    throw Error('ADAPTER_UNAVAILABLE');
  }
  const playbackAllowed=()=>window.__emberboxPlaybackAllowed===true;
  if(request.method==='transport') {
    if(!['toggle','play','pause','next','previous'].includes(p.action))throw Error('INVALID_ARGUMENTS');
    if(p.action!=='pause'&&!playbackAllowed())return {skipped:true};
    if(state.engine) {
      if(p.action==='next'){await state.engine.moveForward();return {ok:true};}
      if(p.action==='previous'){await state.engine.moveBackward();return {ok:true};}
      if(p.action==='toggle'){await state.engine.togglePause();return {ok:true};}
      if(p.action==='pause'){await state.engine.pause();return {ok:true};}
      if(p.action==='play'){await state.engine.resume();return {ok:true};}
    }
    if(external){
      if(p.action==='next'&&external.next){await external.next();return {ok:true};}
      if(p.action==='previous'&&external.prev){await external.prev();return {ok:true};}
      if(external.togglePause){if(p.action==='toggle'||(p.action==='pause'&&playing)||(p.action==='play'&&!playing))await external.togglePause();return {ok:true};}
    }
    if((p.action==='pause'&&!playing)||(p.action==='play'&&playing))return {ok:true};
    const id={next:'NEXT_TRACK_BUTTON',previous:'PREVIOUS_TRACK_BUTTON'}[p.action]||(playing?'PAUSE_BUTTON':'PLAY_BUTTON');
    const control=button(id,bar||document);
    if(control){control.click();return {ok:true};}
    if(media&&['play','pause','toggle'].includes(p.action)){if(p.action==='pause'||(p.action==='toggle'&&playing))media.pause();else await media.play();return {ok:true};}
    throw Error('ADAPTER_UNAVAILABLE');
  }
  if(request.method==='seek') {
    if(typeof p.position!=='number'||!Number.isFinite(p.position)||p.position<0)throw Error('INVALID_ARGUMENTS');
    const value=Math.min(p.position,duration||p.position);
    if(state.engine?.setProgress){await state.engine.setProgress(value);return {ok:true};}
    if(external?.setPosition){await external.setPosition(value);return {ok:true};}
    if(media){media.currentTime=value;return {ok:true};}
    // The HTML slider is controlled by React. Use its existing keyboard handler.
    if(slider){const key=Object.keys(slider).find(k=>k.startsWith('__reactProps$'));const props=key&&slider[key];
      if(typeof props?.onValueChange==='function'){props.onValueChange([value]);return {ok:true};}}
    throw Error('ADAPTER_UNAVAILABLE');
  }
  if(request.method==='wave') {
    if(!playbackAllowed())return {skipped:true};
    if(subscribed===false)throw Error('SUBSCRIPTION_REQUIRED');
    if(status.wave&&playing)return {ok:true};
    if(state.engine) {
      if(status.wave){await state.engine.resume();return {ok:true};}
      await state.engine.playContext({contextData:{type:'vibe',meta:{id:'user:onyourwave'},
        seeds:['user:onyourwave'],from:'emberbox',includeTracksInResponse:true,interactive:true},loadContextMeta:true});
      if(!playbackAllowed())await state.engine.pause();
      return {ok:true};
    }
    await navigate('/');
    const play=await wait(()=>button('MY_VIBE_PLAY_BUTTON')||button('MY_VIBE_PAUSE_BUTTON'));
    if(playbackAllowed()&&!button('MY_VIBE_PAUSE_BUTTON'))play.click();
    return {ok:true};
  }
  if(request.method==='feedback') {
    if(!['like','dislike'].includes(p.action)||!title)throw Error('INVALID_ARGUMENTS');
    const control=button(p.action==='like'?'LIKE_BUTTON':'DISLIKE_BUTTON',bar||document);
    if(!control)throw Error('ADAPTER_UNAVAILABLE');
    control.click();return {ok:true};
  }
  function items() {
    const result=[];const seen=new Set();state.items.clear();
    for(const node of document.querySelectorAll('[data-test-id$="TRACK_TITLE"], [class*="titleLink"][href*="/track/"], a[href*="/track/"]')) {
      const link=node.matches('a[href]')?node:node.querySelector('a[href]');
      let row=node.closest('[role="row"], [class*="HorizontalTrack_root"], [class*="HorizontalCardContainer_root"]')||node.parentElement;
      for(let depth=0;row&&depth<8;depth++,row=row.parentElement)if(button('PLAY_BUTTON',row)||button('PLAY_BUTTON_WITH_COVER',row))break;
      if(!row)continue;
      const url=link?.getAttribute('href')||row.querySelector('a[href*="/track/"]')?.getAttribute('href')||'';
      const match=url.match(/(?:\/track\/|\/tracks\/)(\d+)/);if(!match||seen.has(match[1]))continue;
      const id=match[1],name=text(node);if(!name)continue;seen.add(id);
      const artists=Array.from(row.querySelectorAll('a[href*="/artist/"]')).map(text).filter(Boolean);
      const image=row.querySelector('img');const item={id,title:name,artist:[...new Set(artists)].join(', '),image:cover(image?.src),uri:'yandex:track:'+id};
      state.items.set(id,row);result.push(item);if(result.length>=50)break;
    }
    return result;
  }
  if(request.method==='play') {
    if(!/^\d{1,20}$/.test(String(p.id||'')))throw Error('INVALID_ARGUMENTS');
    if(!playbackAllowed())return {skipped:true};
    const row=state.items.get(String(p.id));
    if(!row?.isConnected)throw Error('NOT_FOUND');
    const control=button('PLAY_BUTTON',row)||button('PLAY_BUTTON_WITH_COVER',row);
    if(!control)throw Error('ADAPTER_UNAVAILABLE');
    control.click();return {ok:true};
  }
  if(request.method==='search') {
    if(typeof p.term!=='string'||!p.term.trim()||p.term.length>200)throw Error('INVALID_ARGUMENTS');
    await navigate('/search?text='+encodeURIComponent(p.term.trim()));
    await wait(()=>document.querySelector('a[href*="/track/"], [data-test-id$="TRACK_TITLE"], [class*="SearchEmpty"]')||test('SEARCH_EMPTY_CONTAINER'));
    return {items:items()};
  }
  if(request.method==='browse') {
    if(!['collection','queue'].includes(p.category))throw Error('INVALID_ARGUMENTS');
    if(p.category==='collection')await navigate('/collection');
    else {const queue=button('PLAY_QUEUE_BUTTON',bar||document);if(queue)queue.click();}
    await wait(()=>document.querySelector('a[href*="/track/"], [data-test-id$="TRACK_TITLE"], [class*="CollectionEmpty"]')||test('COLLECTION_PLAYLIST_WITH_LIKES_EMPTY_BLOCK'));
    return {items:items()};
  }
  throw Error('UNSUPPORTED');
}
