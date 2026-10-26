/* Executed only in the signed-in music.apple.com page. No credentials leave it. */
async function emberboxAppleCommand(request) {
  if (location.origin !== 'https://music.apple.com') throw Error('Apple Music tab required');
  const music = window.MusicKit?.getInstance?.();
  let maximumApplied=false;
  // MusicKit's public HIGH value is a playback preference, never proof of the
  // actual codec/bitrate. Do not lower a future, higher supported setting.
  const high=window.MusicKit?.PlaybackBitrate?.HIGH;
  const identity=String(music?.nowPlayingItem?.id||'');
  const previousMaximum=window.__emberboxMaximumMusic;
  if(music&&Number.isFinite(high)&&high>0&&window.__emberboxPlaybackAllowed!==false) {
    try {
      if(!previousMaximum||previousMaximum.music!==music||previousMaximum.id!==identity||
         ['play','transport'].includes(request.method)) {
        if(Number.isFinite(music.bitrate)&&music.bitrate<high)music.bitrate=high;
        window.__emberboxMaximumMusic={music,id:identity};
      }
      maximumApplied=Number.isFinite(music.bitrate)&&music.bitrate>=high;
    }catch{} // A changed/unsupported setting must not prevent playback.
  }
  if (request.method === 'status') {
    const player = music?.player || music;
    const queue = music?.queue || player?.queue;
    // MusicKit can leave a truthy placeholder in nowPlayingItem after a
    // paused queue restore. Prefer a real queued song over that placeholder.
    const restored=window.__emberboxRestoredTrack;
    const fallback=restored&&restored.music===music?restored.resource:null;
    const candidates=[...(music?.isPlaying!==true?[fallback]:[]),music?.nowPlayingItem,player?.nowPlayingItem,
      queue?.currentItem,queue?.items?.[queue?.position || 0],fallback];
    const current = candidates.find(value=>{
      const a=value?.attributes||value;
      const id=String(value?.id||a?.playParams?.id||'');
      return a&&id!=='-1'&&(id||a.name||a.title);
    });
    const a = current?.attributes || current || {};
    // The website currently supplies audioTraits (atmos/surround), while the
    // public catalogue also uses audioVariants (dolby-atmos/dolby-audio).
    // These are catalogue availability only, never decoder evidence.
    const variantNames=['dolby-atmos','dolby-audio','hi-res-lossless','lossless','lossy-stereo'];
    const aliases={atmos:'dolby-atmos',surround:'dolby-audio'};
    const variants=attributes=>[...new Set(['audioVariants','audioTraits'].flatMap(key=>
      (Array.isArray(attributes?.[key])?attributes[key].slice(0,32):[])
        .filter(v=>typeof v==='string').map(v=>aliases[v]||v).filter(v=>variantNames.includes(v))))];
    const directVariants=variants(a);
    const catalogId=String(a.playParams?.catalogId||current?.catalogId||current?.id||'');
    const cache=window.__emberboxAudioVariants||(window.__emberboxAudioVariants={});
    if(cache.id!==catalogId){cache.id=catalogId;cache.values=[];cache.requested=false;}
    // Extended catalogue attributes are optional. Fetch once per song, without
    // delaying the status/transport response or exposing account credentials.
    const storefront=String(music?.storefrontId||'us');
    if(!directVariants.length&&!cache.requested&&music?.isAuthorized&&typeof music?.api?.music==='function'&&
       /^\d{1,20}$/.test(catalogId)&&/^[a-z]{2}$/.test(storefront)) {
      cache.requested=true;
      Promise.resolve().then(()=>music.api.music(`/v1/catalog/${storefront}/songs/${catalogId}`,{extend:'audioVariants'}))
        .then(result=>{if(cache.id===catalogId)cache.values=variants((result?.data?.data||result?.data||[])[0]?.attributes);})
        .catch(()=>{});
    }
    const metadata = current===fallback ? null : navigator.mediaSession?.metadata;
    const audio = Array.from(document.querySelectorAll('audio,video')).find(m => !m.paused)
      || document.querySelector('audio,video');
    const position = Number(music?.currentPlaybackTime ?? player?.currentPlaybackTime ?? audio?.currentTime ?? 0);
    const duration = Number(music?.currentPlaybackDuration ?? player?.currentPlaybackDuration ?? audio?.duration ?? 0);
    const playing = typeof music?.isPlaying === 'boolean' ? music.isPlaying :
      typeof player?.isPlaying === 'boolean' ? player.isPlaying :
      (window.MusicKit?.PlaybackStates?.playing !== undefined && music?.playbackState === window.MusicKit.PlaybackStates.playing) ||
      navigator.mediaSession?.playbackState === 'playing' || !!(audio && !audio.paused && !audio.ended);
    return {ready:!!music?.api, authorized:!!music?.isAuthorized, musicKit:!!window.MusicKit,
      playing:!!playing, position:!playing && window.__emberboxRestorePosition>0 ? window.__emberboxRestorePosition : Number.isFinite(position)?position:0,
      duration:Number.isFinite(duration)&&duration>0?duration:Number(a.durationInMillis||0)/1000,
      title:String(a.name || a.title || metadata?.title || ''), artist:String(a.artistName || metadata?.artist || ''),
      album:String(a.albumName || metadata?.album || ''), image:image(a.artwork) || String(metadata?.artwork?.[0]?.src || ''),
      id:String(current?.id || a.playParams?.id || ''), catalogId:String(a.playParams?.catalogId || current?.catalogId || ''),
      availableFormats:directVariants.length?directVariants:cache.values||[],
      qualityPreference:{mode:'maximum',applied:maximumApplied},
      url:publicUrl(a.url), canNext:!!music, canPrevious:!!music};
  }
  if (!music?.api) throw Error('MusicKit is not ready. Reload the Apple Music tab and sign in.');
  if (!music.isAuthorized) throw Error('Sign in to Apple Music in this browser first.');
  const params = request.params || {};
  const kinds = ['library-playlists', 'library-albums', 'library-songs', 'songs','albums'];
  const id = String(params.id || '');
  const kind = String(params.kind || '');
  const category = String(params.category || 'playlists');
  const offset = Math.max(0, Math.min(100000, Number(params.offset) || 0));
  const safeId = /^[\w.-]{1,200}$/;

  function publicUrl(value) {
    try { const u=new URL(value);return u.protocol==='https:'&&u.hostname==='music.apple.com'&&!u.username&&!u.password
      ? u.origin+u.pathname : ''; } catch { return ''; }
  }

  function image(art) {
    const value = String(art?.url || '').replace('{w}', '180').replace('{h}', '180').replace('{f}', 'jpg');
    try { return new URL(value).protocol === 'https:' ? value : ''; } catch { return ''; }
  }
  function item(resource) {
    const a = resource.attributes || {};
    return {id: String(resource.id), kind: String(resource.type), title: String(a.name || 'Untitled'),
      subtitle: String(a.artistName || a.curatorName || ''), image: image(a.artwork),
      artist: String(a.artistName || ''), duration_ms: Number(a.durationInMillis || 0),
      uri: `apple:${resource.type}:${resource.id}`, playable: !!a.playParams,
      genres:(a.genreNames||[]).filter(v=>typeof v==='string').slice(0,8),album:String(a.albumName||''),
      releaseDate:String(a.releaseDate||''),trackCount:Number(a.trackCount||0),
      description:String(a.editorialNotes?.standard||a.editorialNotes?.short||'').slice(0,14000),
      copyright:String(a.copyright||''),recordLabel:String(a.recordLabel||''),
      isCompilation:a.isCompilation===true,isSingle:a.isSingle===true};
  }
  async function api(path, query = {}) {
    const catalog=/^\/v1\/catalog\/[a-z]{2}\/(search|songs\/\d{1,20}(\/artists)?|albums\/\d{1,20}(\/tracks)?|artists\/\d{1,20}(\/albums|\/view\/(top-songs|latest-release|full-albums|singles|featured-albums|compilation-albums|appears-on-albums))?)$/;
    const dj=path==='/v1/me/recommendations'||path==='/v1/me/recent/played/tracks'||
      /^\/v1\/catalog\/[a-z]{2}\/playlists\/[\w.-]{1,200}\/tracks$/.test(path);
    if (!path.startsWith('/v1/me/library/') && !catalog.test(path) && !dj) throw Error('Unsupported library request');
    if (typeof music.api.music === 'function') {
      const response = await music.api.music(path, query);
      return response?.data || response || {};
    }
    const library = music.api.library;
    const parts = path.split('/').filter(Boolean).slice(3);
    const type = parts[0];
    if (parts.length === 1) return {data: await library[type]({...query})};
    const singular = {playlists:'playlist',albums:'album',songs:'song'}[type];
    if (parts[2] === 'tracks') return {data: await library[singular+'Relationship'](parts[1], 'tracks', {...query})};
    throw Error('This MusicKit version does not support this operation');
  }
  const player = music.player || music;
  // Documented catalogue relationships keep artist identity tied to a song.
  // No name-based match is silently selected when that relationship is absent.
  function storefront() {
    music.storefrontId=undefined;
    const value=String(music.storefrontId||'us');
    if(!/^[a-z]{2}$/.test(value))throw Error('Invalid request');
    return value;
  }
  function artistItem(resource) {
    const a=resource.attributes||{};
    return {id:String(resource.id),name:String(a.name||'').slice(0,300),
      image:image(a.artwork).replace(/180x180/,'800x800'),genres:(a.genreNames||[]).filter(v=>typeof v==='string').slice(0,8),
      bio:String(a.editorialNotes?.standard||a.editorialNotes?.short||'').slice(0,14000),url:publicUrl(a.url)};
  }
  function page(result) {
    const data=Array.isArray(result)?result:Array.isArray(result?.data)?result.data:[];
    let next=null;
    if(result.next) {try {const value=Number(new URL(result.next,'https://api.music.apple.com').searchParams.get('offset'));
      if(Number.isSafeInteger(value)&&value>offset&&value<=100000)next=value;
    }catch{}}
    return {items:data.filter(r=>['albums','songs'].includes(r.type)).map(item),next};
  }
  // The metadata request's `views` field may omit individual views in the web
  // MusicKit client. Read missing ones through Apple's documented view endpoint,
  // never through a name search or a generic album list relabelled as a category.
  // https://developer.apple.com/documentation/applemusicapi/fetch-a-view-on-this-resource-by-name-4kow5
  const artistViews=[
    {id:'top-songs',view:'top-songs',type:'songs',limit:10},
    {id:'latest-release',view:'latest-release',type:'albums',limit:1},
    {id:'albums',view:'full-albums',type:'albums',limit:8},
    {id:'singles',view:'singles',type:'albums',limit:6},
    {id:'featured-albums',view:'featured-albums',type:'albums',limit:6},
    {id:'compilations',view:'compilation-albums',type:'albums',limit:6},
    {id:'appears',view:'appears-on-albums',type:'albums',limit:6}
  ];
  function artistPage(result,spec) {
    const raw=Array.isArray(result?.data)?result.data:[];const seen=new Set();
    const data=raw.filter(r=>{
      if(!r||r.type!==spec.type||!/^\d{1,20}$/.test(String(r.id))||
         !r.attributes?.name||seen.has(String(r.id)))return false;
      // Reject explicit contradictory flags in the full-album category. The
      // singles view itself is authoritative for EPs, which need not isSingle.
      if(spec.id==='albums'&&(r.attributes.isSingle===true||r.attributes.isCompilation===true))return false;
      seen.add(String(r.id));return true;
    }).slice(0,spec.limit);
    return {id:spec.id,...page({...result,data})};
  }
  async function artistApi(path,query,deadline) {
    const remaining=deadline-Date.now();if(remaining<=0)throw Error('TIMEOUT');
    let timer;
    // MusicKit exposes no AbortSignal here. Its late response is ignored, and
    // every optional view has its own rejection handler before the deadline.
    try {return await Promise.race([api(path,query),new Promise((_,reject)=>{
      timer=setTimeout(()=>reject(Error('TIMEOUT')),remaining);
    })]);}finally{clearTimeout(timer);}
  }
  if(request.method==='artist') {
    const sf=storefront(),deadline=Date.now()+6500;let artistId=id;
    const core=(path,query)=>artistApi(path,query,Math.min(deadline,Date.now()+4500));
    if(artistId&&!/^\d{1,20}$/.test(artistId))throw Error('Invalid artist');
    if(!artistId) {
      const songId=String(params.songId||'');let song;
      const resourceType=['albums','library-albums','album'].includes(String(params.songKind||''))?'albums':'songs';
      if(/^\d{1,20}$/.test(songId)) {
        song=(await core(`/v1/catalog/${sf}/${resourceType}/${songId}`,{include:'artists'})).data?.[0];
      } else if(safeId.test(songId)) {
        try {song=(await core(`/v1/me/library/${resourceType}/${encodeURIComponent(songId)}/catalog`,{include:'artists'})).data?.[0];}catch{}
      }
      const choices=(song?.relationships?.artists?.data||[]).filter(a=>/^\d{1,20}$/.test(String(a.id))).map(artistItem);
      if(choices.length===1)artistId=choices[0].id;
      else if(choices.length)return {choices};
      else {
        const name=String(params.name||'').trim().slice(0,200);
        if(!name)return {choices:[]};
        const result=await core(`/v1/catalog/${sf}/search`,{term:name,types:'artists',limit:12});
        return {choices:(result.results?.artists?.data||[]).map(artistItem)};
      }
    }
    const resource=(await core(`/v1/catalog/${sf}/artists/${artistId}`,
      {views:artistViews.map(s=>s.view).join(','),extend:'editorialNotes'})).data?.[0];
    if(!resource||resource.type!=='artists'||String(resource.id)!==artistId)throw Error('NOT_FOUND');
    const optionalDeadline=Math.min(deadline,Date.now()+2200);
    const sections=await Promise.all(artistViews.map(async spec=>{
      const included=artistPage(resource.views?.[spec.view]||{},spec);
      if(included.items.length)return included;
      try {
        const result=await artistApi(`/v1/catalog/${sf}/artists/${artistId}/view/${spec.view}`,
          {limit:spec.limit},optionalDeadline);
        if(!Array.isArray(result?.data))throw Error('Invalid artist view');
        return artistPage(result,spec);
      }
      catch {return {...included,unavailable:true};}
    }));
    return {artist:artistItem(resource),sections};
  }
  if(request.method==='artistSection') {
    if(params.section==='discography') {
      // Curated views are previews, not the artist's complete release list.
      // Read the albums relationship directly and follow its actual next page.
      const sf=String(params.storefront||storefront()),start=Number(params.offset||0);
      if(!/^\d{1,20}$/.test(id)||!/^[a-z]{2}$/.test(sf)||!Number.isSafeInteger(start)||start<0)throw Error('Invalid artist section');
      const path=`/v1/catalog/${sf}/artists/${id}/albums`;
      const result=await artistApi(path,{limit:100,offset:start},Date.now()+4500);
      if(!Array.isArray(result?.data)||result.errors?.length)throw Error('Invalid artist catalogue');
      let next=null;
      if(result.next) {
        const url=new URL(result.next,'https://api.music.apple.com');
        const cursor=url.searchParams.get('offset');
        if(url.origin!=='https://api.music.apple.com'||url.pathname!==path||!/^\d+$/.test(cursor||''))throw Error('Invalid catalogue continuation');
        next=Number(cursor);
        if(!Number.isSafeInteger(next)||next<=start)throw Error('Invalid catalogue continuation');
      }
      // Retain distinct IDs, including deluxe/clean editions and unplayable
      // releases. Filtering a preview or deduplicating titles loses music.
      if(result.data.some(r=>r.type!=='albums'||!/^\d{1,20}$/.test(String(r.id))||!r.attributes?.name))throw Error('Incomplete artist catalogue response');
      return {id:'discography',catalog:true,storefront:sf,items:result.data.map(item),next};
    }
    const spec=artistViews.find(s=>s.id===params.section);
    if(!/^\d{1,20}$/.test(id)||!spec)throw Error('Invalid artist section');
    const result=await artistApi(`/v1/catalog/${storefront()}/artists/${id}/view/${spec.view}`,
      {limit:24,offset},Date.now()+4500);
    if(!Array.isArray(result?.data))throw Error('Invalid artist view');
    return artistPage(result,{...spec,limit:24});
  }
  if(request.method==='release') {
    const sf=storefront(),deadline=Date.now()+6500;
    const read=(path,query)=>artistApi(path,query,deadline);
    let albumId=id;
    if(!albumId){
      const songId=String(params.songId||'');let song;
      if(/^\d{1,20}$/.test(songId))song=(await read(`/v1/catalog/${sf}/songs/${songId}`,{include:'albums'})).data?.[0];
      else if(/^i\.[\w.-]{1,198}$/.test(songId))song=(await read(`/v1/me/library/songs/${encodeURIComponent(songId)}/catalog`,{include:'albums'})).data?.[0];
      else throw Error('Invalid song');
      if(song?.type!=='songs'||/^\d{1,20}$/.test(songId)&&String(song.id)!==songId)throw Error('NOT_FOUND');
      albumId=String((song?.relationships?.albums?.data||[]).find(a=>a.type==='albums'&&/^\d{1,20}$/.test(String(a.id)))?.id||'');
      if(!albumId)throw Error('NOT_FOUND');
    }
    if(!/^\d{1,20}$/.test(albumId))throw Error('Invalid album');
    const resource=(await read(`/v1/catalog/${sf}/albums/${albumId}`,{extend:'editorialNotes'})).data?.[0];
    if(!resource||resource.type!=='albums'||String(resource.id)!==albumId)throw Error('NOT_FOUND');
    const tracks=offset?await read(`/v1/catalog/${sf}/albums/${albumId}/tracks`,{limit:100,offset}):resource.relationships?.tracks||{};
    return {release:item(resource),...page(tracks)};
  }
  if (request.method === 'search') {
    const term = String(params.term || '').trim().slice(0,200);
    if (!term) return {items:[], next:null};
    music.storefrontId = undefined;
    const storefront = String(music.storefrontId || 'us');
    if (!/^[a-z]{2}$/.test(storefront)) throw Error('Invalid request');
    const types=params.types===undefined?'songs':String(params.types);
    if(!['songs','playlists'].includes(types))throw Error('Invalid search type');
    const result = await api(`/v1/catalog/${storefront}/search`, {term,types,limit:25});
    return {items:(result.results?.[types]?.data || []).map(item),next:null};
  }
  if (request.method === 'transport') {
    const action = params.action;
    if (!['pause','resume','toggle','next','previous'].includes(action)) throw Error('Invalid request');
    if (action !== 'pause' && window.__emberboxPlaybackAllowed === false) return {paused:true};
    if(action==='resume'){await music.play();return {ok:true};}
    if (action === 'pause') await (music.pause ? music.pause() : player.pause());
    else if (action === 'next') {window.__emberboxRestoredTrack=null;window.__emberboxRestorePosition=0;await (music.skipToNextItem ? music.skipToNextItem() : player.skipToNextItem());}
    else if (action === 'previous') {window.__emberboxRestoredTrack=null;window.__emberboxRestorePosition=0;await (music.skipToPreviousItem ? music.skipToPreviousItem() : player.skipToPreviousItem());}
    else {
      const status = await emberboxAppleCommand({method:'status'});
      await (status.playing ? (music.pause ? music.pause() : player.pause()) : (music.play ? music.play() : player.play()));
      if (!status.playing && window.__emberboxRestorePosition>0) {
        await (music.seekToTime ? music.seekToTime(window.__emberboxRestorePosition) : player.seekToTime(window.__emberboxRestorePosition));
        window.__emberboxRestorePosition=0;
      }
    }
    return {ok:true};
  }
  if (request.method === 'seek') {
    const position = Number(params.position);
    if (!Number.isFinite(position) || position < 0) throw Error('Invalid request');
    if (window.__emberboxRestorePosition>0) {window.__emberboxRestorePosition=position;return {ok:true};}
    await (music.seekToTime ? music.seekToTime(position) : player.seekToTime(position));
    return {ok:true};
  }
  if (request.method === 'browse') {
    if(category==='dj') {
      const deadline=Date.now()+5000;
      const results=await Promise.allSettled([
        artistApi('/v1/me/recommendations',{limit:20,include:'contents'},deadline),
        artistApi('/v1/me/recent/played/tracks',{types:'songs,library-songs',limit:30},deadline)]);
      const roots=results[0].status==='fulfilled'?(results[0].value?.data||[]):[];
      const collections=[],songs=[],seen=new Set();
      function visit(resource,depth=0) {
        if(!resource||depth>3)return;
        if(['songs','library-songs','playlists','library-playlists','albums','library-albums'].includes(resource.type)) {
          const key=resource.type+':'+resource.id;
          if(!safeId.test(String(resource.id))||seen.has(key))return;seen.add(key);
          (resource.type.endsWith('songs')?songs:collections).push(item(resource));return;
        }
        for(const child of resource.relationships?.contents?.data||[])visit(child,depth+1);
      }
      for(const value of roots)visit(value);
      const recent=results[1].status==='fulfilled'?(results[1].value?.data||[]):[];
      return {personal:true,items:collections.slice(0,40),tracks:songs.slice(0,50),
        recent:recent.filter(v=>['songs','library-songs'].includes(v.type)).slice(0,30).map(item),
        partial:results.some(v=>v.status==='rejected')};
    }
    if (!['playlists','albums','songs'].includes(category)) throw Error('Unsupported category');
    const result = await api(`/v1/me/library/${category}`, {limit: 50, offset});
    const data = Array.isArray(result) ? result : result.data || [];
    return {items: data.map(item), next: result.next ? offset + data.length : null};
  }
  if (request.method === 'tracks') {
    if (!['library-albums','library-playlists','albums','playlists'].includes(kind) || !safeId.test(id)) throw Error('Invalid collection');
    const collection = kind.replace('library-', '');
    const base=kind.startsWith('library-')?'/v1/me/library':`/v1/catalog/${storefront()}`;
    const result = await api(`${base}/${collection}/${encodeURIComponent(id)}/tracks`, {limit: 100, offset});
    const data = Array.isArray(result) ? result : result.data || [];
    return {tracks: data.map(item), next: result.next ? offset + data.length : null};
  }
  if (request.method === 'play') {
    if (!kinds.includes(kind) || !safeId.test(id)) throw Error('Invalid library item');
    if(params.native===true&&['songs','library-songs'].includes(kind)){
      // The native decoder already owns playback. Hydrate its public metadata
      // without warming up MusicKit's AAC queue on every handover.
      const m=params.metadata||{};
      window.__emberboxRestoredTrack={music,resource:{id,attributes:{name:String(m.title||''),
        artistName:String(m.artist||''),albumName:String(m.album||''),durationInMillis:(Number(m.duration)||0)*1000,
        artwork:{url:String(m.image||'')},audioVariants:Array.isArray(m.availableFormats)?m.availableFormats:[],
        playParams:{id,kind:'song',catalogId:String(m.catalogId||'')}}}};
      window.__emberboxRestorePosition=0;
      if(music.isPlaying)await (music.pause?music.pause():player.pause());
      return {paused:true};
    }
    // MusicKit detects library IDs itself. Its legacy "librarySong" option
    // produces a duplicated /me/library/library-songs path in current builds.
    const queueKind = {'library-songs':'song','songs':'song','albums':'album','library-albums':'album','library-playlists':'playlist'}[kind];
    // An initial public page route can override the account's storefront.
    // Reset only MusicKit's request override, so its documented setter falls
    // back to the signed-in account. The account's country is not changed.
    let stage = 'storefront';
    try {
      music.storefrontId = undefined;
      stage = 'queue';
      window.__emberboxRestoredTrack=null;
      const ids = Array.isArray(params.queue) ? params.queue.filter(value => typeof value === 'string' && safeId.test(value)).slice(0,100) : [];
      await music.setQueue(['library-songs','songs'].includes(kind) && ids.includes(id)
        ? {songs:ids,startWith:ids.indexOf(id)} : {[queueKind]:id});
      window.__emberboxRestorePosition=Number.isFinite(params.position)&&params.position>0?params.position:0;
      if(params.paused===true){
        await (music.pause ? music.pause() : player.pause());
        // setQueue may not hydrate any MusicKit items until play(). Keep the
        // requested song visible without starting audio or blocking status.
        const restored={music,resource:{id,attributes:{}}};
        window.__emberboxRestoredTrack=restored;
        if(['songs','library-songs'].includes(kind))Promise.resolve().then(()=>api(
          kind==='library-songs'?`/v1/me/library/songs/${id}`:`/v1/catalog/${storefront()}/songs/${id}`))
          .then(result=>{const resource=(Array.isArray(result)?result:result.data||[])[0];
            if(window.__emberboxRestoredTrack===restored&&resource?.attributes)restored.resource=resource;})
          .catch(()=>{});
        return {paused:true};
      }
      if (window.__emberboxPlaybackAllowed === false) return {paused:true};
      stage = 'start';
      await music.play();
      if(window.__emberboxRestorePosition>0){
        await music.seekToTime(window.__emberboxRestorePosition);
        window.__emberboxRestorePosition=0;
      }
    } catch (error) {
      error.emberboxStage = stage;
      throw error;
    }
    return {playing:true};
  }
  throw Error('Unsupported operation');
}
