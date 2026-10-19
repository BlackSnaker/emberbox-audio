/* Executed only in the signed-in music.apple.com page. No credentials leave it. */
async function emberboxAppleCommand(request) {
  if (location.origin !== 'https://music.apple.com') throw Error('Apple Music tab required');
  const music = window.MusicKit?.getInstance?.();
  if (!music?.api) throw Error('MusicKit is not ready. Reload the Apple Music tab and sign in.');
  if (!music.isAuthorized) throw Error('Sign in to Apple Music in this browser first.');
  const params = request.params || {};
  const kinds = ['library-playlists', 'library-albums', 'library-songs'];
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
    if (!path.startsWith('/v1/me/library/')) throw Error('Unsupported library request');
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
  if (request.method === 'status') return {connected: true};
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
    const queueKind = {'library-songs':'librarySong','library-albums':'album','library-playlists':'playlist'}[kind];
    await music.setQueue({[queueKind]:id, parameters:{isLibrary:true}});
    await music.play();
    return {playing:true};
  }
  throw Error('Unsupported operation');
}
