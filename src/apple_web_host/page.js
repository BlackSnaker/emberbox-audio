/* Executed only in the signed-in music.apple.com page. No credentials leave it. */
async function emberboxAppleCommand(request) {
  if (location.origin !== 'https://music.apple.com') throw Error('Apple Music tab required');
  const music = window.MusicKit?.getInstance?.();
  if (request.method === 'status') {
    const player = music?.player || music;
    const queue = music?.queue || player?.queue;
    const current = music?.nowPlayingItem || player?.nowPlayingItem || queue?.currentItem || queue?.items?.[queue.position || 0];
    const a = current?.attributes || current || {};
    const metadata = navigator.mediaSession?.metadata;
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
      id:String(current?.id || a.playParams?.id || ''), canNext:!!music, canPrevious:!!music};
  }
  if (!music?.api) throw Error('MusicKit is not ready. Reload the Apple Music tab and sign in.');
  if (!music.isAuthorized) throw Error('Sign in to Apple Music in this browser first.');
  const params = request.params || {};
  const kinds = ['library-playlists', 'library-albums', 'library-songs', 'songs'];
  const id = String(params.id || '');
  const kind = String(params.kind || '');
  const category = String(params.category || 'playlists');
  const offset = Math.max(0, Math.min(100000, Number(params.offset) || 0));
  const safeId = /^[\w.-]{1,200}$/;

  function image(art) {
    const value = String(art?.url || '').replace('{w}', '180').replace('{h}', '180').replace('{f}', 'jpg');
    try { return new URL(value).protocol === 'https:' ? value : ''; } catch { return ''; }
  }
  function item(resource) {
    const a = resource.attributes || {};
    return {id: String(resource.id), kind: String(resource.type), title: String(a.name || 'Untitled'),
      subtitle: String(a.artistName || a.curatorName || ''), image: image(a.artwork),
      artist: String(a.artistName || ''), duration_ms: Number(a.durationInMillis || 0),
      uri: `apple:${resource.type}:${resource.id}`, playable: !!a.playParams};
  }
  async function api(path, query = {}) {
    if (!path.startsWith('/v1/me/library/') && !/^\/v1\/catalog\/[a-z]{2}\/search$/.test(path)) throw Error('Unsupported library request');
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
  if (request.method === 'search') {
    const term = String(params.term || '').trim().slice(0,200);
    if (!term) return {items:[], next:null};
    music.storefrontId = undefined;
    const storefront = String(music.storefrontId || 'us');
    if (!/^[a-z]{2}$/.test(storefront)) throw Error('Invalid request');
    const result = await api(`/v1/catalog/${storefront}/search`, {term,types:'songs',limit:25});
    return {items:(result.results?.songs?.data || []).map(item),next:null};
  }
  if (request.method === 'transport') {
    const action = params.action;
    if (!['pause','toggle','next','previous'].includes(action)) throw Error('Invalid request');
    if (action !== 'pause' && window.__emberboxPlaybackAllowed === false) return {paused:true};
    if (action === 'pause') await (music.pause ? music.pause() : player.pause());
    else if (action === 'next') {window.__emberboxRestorePosition=0;await (music.skipToNextItem ? music.skipToNextItem() : player.skipToNextItem());}
    else if (action === 'previous') {window.__emberboxRestorePosition=0;await (music.skipToPreviousItem ? music.skipToPreviousItem() : player.skipToPreviousItem());}
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
    if (!['playlists','albums','songs'].includes(category)) throw Error('Unsupported category');
    const result = await api(`/v1/me/library/${category}`, {limit: 50, offset});
    const data = Array.isArray(result) ? result : result.data || [];
    return {items: data.map(item), next: result.next ? offset + data.length : null};
  }
  if (request.method === 'tracks') {
    if (!['library-albums','library-playlists'].includes(kind) || !safeId.test(id)) throw Error('Invalid collection');
    const collection = kind.replace('library-', '');
    const result = await api(`/v1/me/library/${collection}/${encodeURIComponent(id)}/tracks`, {limit: 100, offset});
    const data = Array.isArray(result) ? result : result.data || [];
    return {tracks: data.map(item), next: result.next ? offset + data.length : null};
  }
  if (request.method === 'play') {
    if (!kinds.includes(kind) || !safeId.test(id)) throw Error('Invalid library item');
    // MusicKit detects library IDs itself. Its legacy "librarySong" option
    // produces a duplicated /me/library/library-songs path in current builds.
    const queueKind = {'library-songs':'song','songs':'song','library-albums':'album','library-playlists':'playlist'}[kind];
    // An initial public page route can override the account's storefront.
    // Reset only MusicKit's request override, so its documented setter falls
    // back to the signed-in account. The account's country is not changed.
    let stage = 'storefront';
    try {
      music.storefrontId = undefined;
      stage = 'queue';
      const ids = Array.isArray(params.queue) ? params.queue.filter(value => typeof value === 'string' && safeId.test(value)).slice(0,100) : [];
      await music.setQueue(['library-songs','songs'].includes(kind) && ids.includes(id)
        ? {songs:ids,startWith:ids.indexOf(id)} : {[queueKind]:id});
      window.__emberboxRestorePosition=Number.isFinite(params.position)&&params.position>0?params.position:0;
      if(params.paused===true)return {paused:true};
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
