/* Typed metadata/control adapter for the official Yandex Music website.
 * Authentication and recommendation feedback stay in the site's own session.
 * Never return a store snapshot, requests, tokens, cookies or account details.
 */
async function emberboxYandexCommand(request) {
  if (location.origin !== 'https://music.yandex.ru') throw Error('NOT_READY');
  const allowed=['status','wave','browse','tracks','search','play','transport','seek','feedback','artist','artistSection','release'];
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
  function fibers(element,visit) {
    const key=Object.keys(element||{}).find(key=>key.startsWith('__reactFiber$')||key.startsWith('__reactInternalInstance$'));
    let fiber=key&&element[key];
    for(let depth=0;fiber&&depth<180;depth++,fiber=fiber.return) {
      const props=fiber.memoizedProps||{};
      visit(props.value,props);
      // useContext consumers retain their provider values here, even when
      // the provider itself is above the inspected DOM subtree.
      let dependency=fiber.dependencies?.firstContext;
      for(let i=0;dependency&&i<24;i++,dependency=dependency.next)
        visit(dependency.memoizedValue,props);
    }
  }
  function context() {
    const found={};
    const accept=value=>{
      try {
        if(value?.user&&value?.sonataState)found.store=value;
        if(value&&typeof value.togglePause==='function'&&typeof value.playContext==='function')found.engine=value;
        if(value&&typeof value.push==='function'&&typeof value.replace==='function'&&typeof value.prefetch==='function')found.router=value;
        if(value&&typeof value.setQuality==='function'&&value.quality&&
           ['high_quality','balanced','efficient','preview'].includes(value.quality.value))found.qualityController=value;
      }catch{} // A detached MobX provider must not hide the live provider.
    };
    // Start with the actual player, which can be outside <main>. Re-read
    // contexts after login/navigation instead of keeping the guest store.
    const anchors=[...document.querySelectorAll('[data-test-id$="PLAYERBAR_DESKTOP"], [data-test-id$="VIBE_PLAYERBAR"], [class*="PlayerBar_root"], [class*="PlayerBarDesktop_root"], main, body > div')];
    const nodes=[...anchors,...Array.from(document.querySelectorAll('main,main *,body > div')).slice(0,120)];
    for(const element of new Set(nodes))fibers(element,accept);
    if(found.store&&found.store!==state.store&&!found.qualityController)delete state.qualityController;
    Object.assign(state,found);
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
  const authorized=user?.isAuthorized===true||!!test('USER_PROFILE_USERNAME');
  const subscribed=typeof user?.hasPlus==='boolean'?user.hasPlus:null;
  let maximumApplied=false;
  // Use the same two setters as the official site's "High quality" control.
  // high_quality lets Yandex select Lossless where the song/account support it.
  if(authorized&&subscribed===true&&window.__emberboxPlaybackAllowed!==false) {
    try {
      const quality=state.qualityController;
      if(typeof quality?.setQuality==='function'&&typeof view?.setQuality==='function') {
        if(quality.quality.value!=='high_quality')quality.setQuality('high_quality');
        if(view.quality!=='high_quality')view.setQuality('high_quality');
        maximumApplied=quality.quality.value==='high_quality'&&view.quality==='high_quality';
      }
    }catch{} // Subscription/adapter changes keep the existing stream available.
  }
  const status={ready:document.readyState==='complete'&&!!(state.store||external||bar||button('MY_VIBE_PLAY_BUTTON')||test('USER_PROFILE_USERNAME')),authorized,subscribed,regionBlocked:region,
    capabilities:{player:!!state.engine,wave:!!state.engine?.playContext||!!button('MY_VIBE_PLAY_BUTTON'),
      navigation:!!state.router,metadata:!!(view||meta||extTrack),store:!!state.store,legacy:!!external},
    playing:!!playing,title,artist,album:String(meta?.album||track?.mainAlbum?.title||extTrack?.album?.title||'').slice(0,300),
    id:String(track?.id||extTrack?.id||title).slice(0,300),image:cover(rawCover),duration,position,
    canNext:!!view?.canMoveForward||!!button('NEXT_TRACK_BUTTON')||!!external?.next,
    canPrevious:!!view?.canMoveBackward||!!button('PREVIOUS_TRACK_BUTTON')||!!external?.prev,
    wave:!!state.store?.sonataState?.isVibeContext||!!button('MY_VIBE_PAUSE_BUTTON'),
    qualityPreference:{mode:'maximum',applied:maximumApplied,reason:subscribed===false?'subscription':maximumApplied?'':'adapter'}};
  status.artists=(Array.isArray(track?.artists)?track.artists:Array.isArray(extTrack?.artists)?extTrack.artists:[])
    .filter(a=>/^\d{1,20}$/.test(String(a.id||''))).slice(0,12)
    .map(a=>({id:String(a.id),name:String(a.name||a.title||'').slice(0,300)}));
  if(request.method==='status')return status;
  if(region)throw Error('REGION_UNAVAILABLE');
  if(!authorized)throw Error('SIGN_IN_REQUIRED');
  const playlistRoute=value=>{
    if(typeof value!=='string')return '';
    try {
      const url=new URL(value,location.origin);
      if(url.origin!==location.origin||url.search||url.hash)return '';
      return /^\/playlists\/[a-zA-Z0-9-]{1,100}$/.test(url.pathname)||
        /^\/users\/[\w.@-]{1,100}\/playlists\/\d{1,20}$/.test(url.pathname)?url.pathname:'';
    }catch{return '';}
  };
  async function navigate(route,preserve=false) {
    if(location.pathname+location.search===route)return;
    context();
    if(state.router){state.router.push(route);await wait(()=>location.pathname+location.search===route);return;}
    const link=Array.from(document.querySelectorAll('a[href]')).find(a=>a.getAttribute('href')===route);
    if(link){link.click();await wait(()=>location.pathname+location.search===route);return;}
    // The host reloads the same official site, then reinjects this adapter.
    if(preserve)throw Error('ADAPTER_UNAVAILABLE');
    const error=Error('NAVIGATION_REQUIRED');error.emberboxRoute=route;throw error;
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
    const waveControl=button('MY_VIBE_PLAY_BUTTON');
    if(waveControl){waveControl.click();return {ok:true};}
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
  const listRoot=()=>document.querySelector('main')||document;
  function items(root=listRoot()) {
    const result=[];const seen=new Set();state.items.clear();
    for(const node of root.querySelectorAll('[data-test-id$="TRACK_TITLE"], [class*="titleLink"][href*="/track/"], a[href*="/track/"]')) {
      const link=node.matches('a[href]')?node:node.querySelector('a[href]');
      let row=node.closest('[role="row"], [class*="HorizontalTrack_root"], [class*="HorizontalCardContainer_root"]')||node.parentElement;
      if(!row)continue;
      const url=link?.getAttribute('href')||row.querySelector('a[href*="/track/"]')?.getAttribute('href')||'';
      const match=url.match(/(?:\/track\/|\/tracks\/)(\d+)/);if(!match||seen.has(match[1]))continue;
      const id=match[1],name=text(node);if(!name)continue;seen.add(id);
      const artists=Array.from(row.querySelectorAll('a[href*="/artist/"]')).map(text).filter(Boolean);
      const image=row.querySelector('img');const item={id,kind:'track',title:name,artist:[...new Set(artists)].join(', '),image:cover(image?.src),uri:'yandex:track:'+id};
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
    if(control){
      // PLAY_BUTTON_WITH_COVER is a wrapper on the modern site.
      const target=control.matches?.('button')?control:control.querySelector('button');
      if(visible(target)){target.click();return {ok:true};}
      const propsKey=Object.keys(control).find(key=>key.startsWith('__reactProps$'));
      if(typeof control[propsKey]?.onClick==='function'){control.click();return {ok:true};}
    }
    let params=null;
    const titleNode=row.querySelector('[data-test-id$="TRACK_TITLE"], a[href*="/track/"]')||row;
    fibers(titleNode,(_value,props)=>{if(!params&&props.playContextParams)params=props.playContextParams;});
    if(params&&state.engine){await state.engine.playContext(params);if(!playbackAllowed())await state.engine.pause();return {ok:true};}
    throw Error('ADAPTER_UNAVAILABLE');
  }
  function playlists() {
    const result=[],seen=new Set();
    for(const node of listRoot().querySelectorAll('[data-test-id$="PLAYLIST_TITLE"], a[href*="/playlists/"]')) {
      const link=node.matches('a[href]')?node:node.querySelector('a[href]');
      const route=playlistRoute(link?.getAttribute('href'));if(!route||seen.has(route))continue;
      const name=text(node);if(!name)continue;seen.add(route);
      const row=node.closest('[data-test-id$="PLAYLIST_ITEM"], [data-test-id$="PLAYLIST_CARD"], [class*="PlaylistCard_root"], [class*="HorizontalCardContainer_root"]')||node.parentElement;
      const image=row?.querySelector('img');
      result.push({id:route,kind:'playlist',title:name,artist:'',image:cover(image?.src)});
      if(result.length>=50)break;
    }
    return result;
  }
  const trackSelector='a[href*="/track/"], [data-test-id$="TRACK_TITLE"]';
  const emptyTracks=()=>document.querySelector('[class*="SearchEmpty"], [class*="CollectionEmpty"], [data-test-id$="EMPTY_TITLE"], [data-test-id$="EMPTY_ROOT"]')||test('SEARCH_EMPTY_CONTAINER')||test('COLLECTION_PLAYLIST_WITH_LIKES_EMPTY_BLOCK');
  function artistLinks(root=listRoot()) {
    const seen=new Set();return Array.from(root.querySelectorAll('a[href*="/artist/"]')).map(a=>({
      id:a.getAttribute('href')?.match(/^\/artist\/(\d{1,20})$/)?.[1],name:text(a),
      image:cover(a.closest('[class*="ArtistCard"], [class*="HorizontalCard"]')?.querySelector('img')?.src)
    })).filter(a=>a.id&&a.name&&!seen.has(a.id)&&seen.add(a.id)).slice(0,20);
  }
  function albums() {
    const result=[],seen=new Set();
    for(const link of listRoot().querySelectorAll('a[href*="/album/"]')) {
      const id=link.getAttribute('href')?.match(/^\/album\/(\d{1,20})$/)?.[1];
      if(!id||seen.has(id))continue;
      const card=link.closest('[class*="AlbumCard"], [class*="HorizontalCard"], [data-test-id$="ALBUM_ITEM"]');
      if(!card)continue;
      const name=text(card.querySelector('[data-test-id$="ALBUM_TITLE"]')||link);
      if(!name)continue;seen.add(id);
      result.push({id,kind:'album',uri:'yandex:album:'+id,title:name,image:cover(card.querySelector('img')?.src),
        subtitle:text(card.querySelector('[class*="metadata"], [class*="description"]'))});
      if(result.length>=100)break;
    }
    return result;
  }
  if(request.method==='artist') {
    let id=String(p.id||'');
    if(!id) {
      const own=String(p.songId||'')===status.id?status.artists:[];
      const choices=own.length?own:(!p.songId||String(p.songId)===status.id?artistLinks(bar||listRoot()):[]);
      if(choices.length===1&&own.length)id=choices[0].id;
      else if(choices.length)return {choices};
      else {
        const name=String(p.name||'').trim().slice(0,200);if(!name)return {choices:[]};
        await navigate('/search?text='+encodeURIComponent(name),true);
        await wait(()=>listRoot().querySelector('a[href*="/artist/"]')||emptyTracks());
        return {choices:artistLinks()};
      }
    }
    if(!/^\d{1,20}$/.test(id))throw Error('INVALID_ARGUMENTS');
    await navigate('/artist/'+id,true);await wait(()=>listRoot().querySelector('h1'));
    const root=listRoot(),hero=root.querySelector('[class*="ArtistPage"]')||root;
    const artist={id,name:text(root.querySelector('h1')),image:cover(hero.querySelector('[class*="ArtistPage"] img, [class*="ArtistHeader"] img, [class*="PageHeader"] img')?.src),
      bio:String(root.querySelector('[class*="ArtistAbout"] [class*="description"], [class*="ArtistDescription"], [data-test-id$="ARTIST_DESCRIPTION"]')?.textContent||'').trim().slice(0,14000),genres:[]};
    return {artist,sections:[{id:'top-songs',items:items()},{id:'latest-release',items:albums()}],
      note:'Показаны данные, загруженные официальным сайтом Яндекс Музыки.'};
  }
  if(request.method==='artistSection') {
    const id=String(p.id||'');if(!/^\d{1,20}$/.test(id)||!['albums','singles','compilations','appears'].includes(p.section))throw Error('INVALID_ARGUMENTS');
    await navigate('/artist/'+id,true);await wait(()=>listRoot().querySelector('h1'));
    const suffix={albums:'albums',singles:'singles',compilations:'compilations',appears:'appears-on'}[p.section];
    const link=Array.from(listRoot().querySelectorAll('a[href]')).find(a=>a.getAttribute('href')==='/artist/'+id+'/'+suffix);
    if(link){await navigate(link.getAttribute('href'),true);await wait(()=>listRoot().querySelector('a[href*="/album/"]')||emptyTracks());}
    else if(p.section!=='albums')return {items:[],note:'Этот раздел не передан сайтом для данного артиста.'};
    return {items:albums(),next:null,note:'Показаны загруженные сайтом релизы; отдельные категории доступны только когда сайт их предоставляет.'};
  }
  if(request.method==='release') {
    const id=String(p.id||'');if(!/^\d{1,20}$/.test(id))throw Error('INVALID_ARGUMENTS');
    await navigate('/album/'+id,true);await wait(()=>listRoot().querySelector(trackSelector)||emptyTracks());
    const root=listRoot();
    return {release:{id,kind:'album',uri:'yandex:album:'+id,title:text(root.querySelector('h1')),
      artist:artistLinks().map(a=>a.name).join(', '),image:cover(root.querySelector('[class*="AlbumPage"] img, [class*="PageHeader"] img')?.src),
      description:String(root.querySelector('[class*="AlbumDescription"]')?.textContent||'').trim().slice(0,14000)},items:items(),next:null};
  }
  if(request.method==='tracks') {
    const route=playlistRoute(p.id);if(!route)throw Error('INVALID_ARGUMENTS');
    await navigate(route);
    await wait(()=>listRoot().querySelector(trackSelector)||emptyTracks());
    return {items:items()};
  }
  if(request.method==='search') {
    if(typeof p.term!=='string'||!p.term.trim()||p.term.length>200)throw Error('INVALID_ARGUMENTS');
    await navigate('/search?text='+encodeURIComponent(p.term.trim()));
    await wait(()=>listRoot().querySelector('a[href*="/track/"], [data-test-id$="TRACK_TITLE"], [class*="SearchEmpty"]')||test('SEARCH_EMPTY_CONTAINER'));
    return {items:items()};
  }
  if(request.method==='browse') {
    if(!['collection','queue'].includes(p.category))throw Error('INVALID_ARGUMENTS');
    if(p.category==='collection') {
      await navigate('/collection/playlists');
      await wait(()=>listRoot().querySelector('[data-test-id$="PLAYLIST_TITLE"], a[href*="/playlists/"], [class*="CollectionEmpty"], [data-test-id$="EMPTY_TITLE"], [data-test-id$="EMPTY_ROOT"]'));
      return {items:playlists()};
    }
    const queue=button('PLAY_QUEUE_BUTTON',bar||document);if(queue)queue.click();
    await wait(()=>document.querySelector(trackSelector)||emptyTracks());
    return {items:items(document)};
  }
  throw Error('UNSUPPORTED');
}
