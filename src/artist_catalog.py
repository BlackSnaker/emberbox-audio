"""Source-owned artist metadata, requested only after opening an artist page."""
from html.parser import HTMLParser
import re
from source_picker import text

SECTIONS=('overview','discography','albums','singles','compilations','appears','about')
APPLE_VIEWS={'albums':'full-albums','singles':'singles',
             'compilations':'compilation-albums','appears':'appears-on-albums'}


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.hidden+=1
        if tag in ('p','br','div') and not self.hidden:self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
        if tag in ('p','div') and not self.hidden:self.parts.append('\n')
    def handle_data(self,value):
        if not self.hidden:self.parts.append(value)


def plain(value,limit=14000):
    parser=PlainText();parser.feed(str(value or '')[:limit*2]);parser.close()
    value=''.join(parser.parts).replace('\r','')
    return re.sub(r'\n[ \t]*\n+', '\n\n',value).strip()[:limit]


def artist_ref(host,item=None):
    """Capture the clicked recording, not mutable host state inside a worker."""
    if item:
        return {'name':str(item.get('artist') or item.get('subtitle') or '')[:300],
                'songId':str(item.get('id') or item.get('uri','').rsplit(':',1)[-1])[:200],
                'songKind':str(item.get('kind') or ''),'songUri':str(item.get('uri') or '')[:300]}
    ref={'name':host.artist.get_text()[:300],'current':True}
    if host.source=='spotify' and getattr(host,'spotify_mode','desktop')=='native':
        state=host.spotify_web.state;ref.update(songUri=str(state.get('uri') or ''),songId=str(state.get('id') or ''))
        artists=state.get('artists') or []
        if len(artists)==1:ref.update(id=artists[0]['id'],name=artists[0]['name'])
    elif host.source=='apple-music' and host.apple_mode=='native':
        state=host.apple_web.state
        ref.update(songId=str(state.get('catalogId') or state.get('id') or ''),songKind='songs')
    elif host.source=='yandex-music':
        state=host.yandex_web.state;ref['songId']=str(state.get('id') or '')
        artists=state.get('artists') or []
        if len(artists)==1:ref.update(id=str(artists[0].get('id') or ''),name=str(artists[0].get('name') or ref['name']))
    elif getattr(host,'session',None):
        ref['songUri']=str(host.session.metadata.get('xesam:url') or '')[:300]
    return ref


def album_ref(host):
    """Snapshot the recording whose album label was clicked; never name-search."""
    source=host.source
    title=host.album.get_text().strip()
    if source not in ('spotify','apple-music','yandex-music') or not title or not host.length:return None
    if source=='apple-music' and host.apple_mode!='native':return None
    ref=artist_ref(host)
    ref.update(name=title[:300],title=title[:300],artist=host.artist.get_text()[:300],kind='album')
    if source in ('apple-music','yandex-music'):
        state=(host.apple_web if source=='apple-music' else host.yandex_web).state
        if state.get('album')!=title:return None  # The label may contain a connection error.
        album_id=str(state.get('albumId') or '')
        if re.fullmatch(r'\d{1,20}',album_id):ref['id']=album_id
    elif source=='spotify' and getattr(host,'spotify_mode','desktop')=='native':
        state=host.spotify_web.state
        if state.get('albumId'):ref['id']=str(state['albumId'])
        else:ref.pop('id',None)
    elif not ref.get('songUri'):
        ident=str(getattr(host,'track_id','') or '').rsplit('/',1)[-1]
        if re.fullmatch(r'[A-Za-z0-9]{1,64}',ident):ref['songUri']='spotify:track:'+ident
    return ref


def release_details(release,reference,items):
    """Keep source album facts; a track/artist room isn't album-artist proof."""
    release=release or {};reference=reference or {};value={**reference,**release}
    for field in ('title','image'):
        if not value.get(field) and reference.get(field):value[field]=reference[field]
    artist=release.get('artist') or (reference.get('artist') if not reference.get('current') else '')
    if not artist:
        artists={item.get('artist') for item in items if item.get('artist')}
        artist=next(iter(artists)) if len(artists)==1 else ''
    value['artist']=artist
    for field in ('artistId','artistUri'):
        ident=release.get(field) or (reference.get(field) if not reference.get('current') else '')
        if ident and artist:value[field]=ident
        else:value.pop(field,None)
    return value


def sanitize(result):
    """Render provider prose as text; never interpret remote markup as GTK markup."""
    if not isinstance(result,dict):raise ValueError('Invalid artist response')
    result=dict(result)
    for key in ('artist','release'):
        if isinstance(result.get(key),dict):
            result[key]=dict(result[key]);result[key]['bio']=plain(result[key].get('bio'))
            result[key]['description']=plain(result[key].get('description'))
    # This is a per-response guard, never a limit on an accumulated catalogue.
    # Refuse oversized pages rather than silently losing their continuation.
    result['items']=list(result.get('items') or [])
    if len(result['items'])>200:raise ValueError('Artist page is too large; retry with smaller pages')
    result['choices']=list(result.get('choices') or [])[:20]
    for section in result.get('sections') or []:section['items']=list(section.get('items') or [])[:30]
    return result


class ReleaseCatalog:
    """One artist/storefront scan, resumable between individually bounded calls."""
    def __init__(self):
        self.items=[];self.seen=set();self.offset=0;self.complete=False
        self.storefront='';self.error='';self.pages=0
        self.stalled_pages=0;self.single_ids=set()

    def accept(self,result,offset):
        if offset!=self.offset or self.complete:raise ValueError('Unexpected catalogue page')
        sf=result.get('storefront')
        if not result.get('catalog') or not isinstance(sf,str) or not re.fullmatch('[a-z]{2}',sf):
            raise ValueError('Invalid catalogue page')
        if self.storefront and sf!=self.storefront:raise ValueError('Catalogue region changed; refresh the artist')
        next_offset=result.get('next')
        if next_offset is not None and (type(next_offset) is not int or next_offset<=offset):
            raise ValueError('Catalogue did not advance; retry the page')
        values=result.get('items') or []
        progress=any((v.get('uri') or v.get('id')) not in self.seen for v in values)
        stalled=0 if progress else self.stalled_pages+1
        if next_offset is not None and stalled>=3:raise ValueError('Catalogue returned repeated empty or duplicate pages; retry')
        self.storefront=sf
        self.stalled_pages=stalled
        for value in values:
            key=value.get('uri') or value.get('id')
            if key and key not in self.seen:self.seen.add(key);self.items.append(value)
        self.pages+=1;self.complete=next_offset is None;self.error=''
        if next_offset is not None:self.offset=next_offset

    def selection(self,section,single_ids=()):
        single_ids=self.single_ids|set(single_ids)
        def single(value):
            # Apple labels EPs in release titles; its isSingle flag only means
            # one song. Included singles-view IDs are also source evidence.
            return value.get('isSingle') or value.get('id') in single_ids or bool(re.search(r'\s[-–—]\sEP$',value.get('title',''),re.I))
        if section=='discography':return self.items
        if section=='compilations':return [v for v in self.items if v.get('isCompilation')]
        if section=='singles':return [v for v in self.items if not v.get('isCompilation') and single(v)]
        return [v for v in self.items if not v.get('isCompilation') and not single(v)]


class ArtistRepository:
    def __init__(self,host):self.host=host

    def load(self,source,category,ref,offset=0):
        ref=dict(ref or {});method={'artist':'artist','artist-section':'artistSection','release':'release'}[category]
        if source=='apple-music':
            if self.host.apple_mode!='native':
                raise RuntimeError(text('Connect the in-player Apple Music source in Accounts to explore artists.',
                                        'Подключи встроенную Apple Music в Аккаунтах, чтобы открыть артистов.'))
            player=self.host.apple_web
        elif source=='yandex-music':player=self.host.yandex_web
        elif source=='spotify' and getattr(self.host,'spotify_mode','desktop')=='native':player=self.host.spotify_web
        elif source=='spotify':
            from discovery import LocalSpotify
            from spotify_artist import SpotifyArtist
            with LocalSpotify() as client:return sanitize(SpotifyArtist(client).load(category,ref,offset))
        else:
            return {'artist':{'id':'','name':str(ref.get('name') or 'YouTube'),'image':'','bio':''},
                    'items':[],'sections':[], 'searchOnly':True,
                    'note':text('This YouTube connection exposes videos, not a verified artist discography. Search this name to keep listening.',
                                'Это подключение YouTube показывает видео, а не подтверждённую дискографию артиста. Найди это имя, чтобы продолжить слушать.')}
        params={key:ref[key] for key in ('id','name','songId','songKind','songUri','section','storefront') if key in ref}
        params['offset']=offset
        return sanitize(player.request(method,**params))
