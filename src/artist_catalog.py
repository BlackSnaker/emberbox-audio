"""Source-owned artist metadata, requested only after opening an artist page."""
from html.parser import HTMLParser
import re
from source_picker import text

SECTIONS=('overview','albums','singles','compilations','appears','about')
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
    if host.source=='apple-music' and host.apple_mode=='native':
        state=host.apple_web.state
        ref.update(songId=str(state.get('catalogId') or state.get('id') or ''),songKind='songs')
    elif host.source=='yandex-music':
        state=host.yandex_web.state;ref['songId']=str(state.get('id') or '')
        artists=state.get('artists') or []
        if len(artists)==1:ref.update(id=str(artists[0].get('id') or ''),name=str(artists[0].get('name') or ref['name']))
    elif getattr(host,'session',None):
        ref['songUri']=str(host.session.metadata.get('xesam:url') or '')[:300]
    return ref


def sanitize(result):
    """Render provider prose as text; never interpret remote markup as GTK markup."""
    if not isinstance(result,dict):raise ValueError('Invalid artist response')
    result=dict(result)
    for key in ('artist','release'):
        if isinstance(result.get(key),dict):
            result[key]=dict(result[key]);result[key]['bio']=plain(result[key].get('bio'))
            result[key]['description']=plain(result[key].get('description'))
    result['items']=list(result.get('items') or [])[:200]
    result['choices']=list(result.get('choices') or [])[:20]
    for section in result.get('sections') or []:section['items']=list(section.get('items') or [])[:30]
    return result


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
        elif source=='spotify':
            from discovery import LocalSpotify
            from spotify_artist import SpotifyArtist
            with LocalSpotify() as client:return sanitize(SpotifyArtist(client).load(category,ref,offset))
        else:
            return {'artist':{'id':'','name':str(ref.get('name') or 'YouTube'),'image':'','bio':''},
                    'items':[],'sections':[], 'searchOnly':True,
                    'note':text('This YouTube connection exposes videos, not a verified artist discography. Search this name to keep listening.',
                                'Это подключение YouTube показывает видео, а не подтверждённую дискографию артиста. Найди это имя, чтобы продолжить слушать.')}
        params={key:ref[key] for key in ('id','name','songId','songKind','songUri','section') if key in ref}
        params['offset']=offset
        return sanitize(player.request(method,**params))
