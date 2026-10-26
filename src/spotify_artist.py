"""Read artist/release pages through the already connected Spotify desktop UI.

This optional adapter uses the same version-dependent connection as discovery.
Only whitelisted music fields leave the client; navigation never starts playback.
"""
import json
import re
import time
from source_picker import text
from discovery import image_url

NAVIGATE=r'''(() => {
  const path=PATH;
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
})()'''

REFERENCES=r'''(() => {
  const uri=URI,current=CURRENT,seen=new Set(),result=[];
  const id=uri.match(/(?:spotify:track:|\/track\/)([A-Za-z0-9]+)/)?.[1];
  const row=id?Array.from(document.querySelectorAll('main [data-testid="tracklist-row"]'))
    .find(row=>row.querySelector('a[href="/track/'+id+'"]')):null;
  const footer=current?document.querySelector('footer, [data-testid="now-playing-widget"]'):null;
  const currentId=footer?.querySelector('a[href^="/track/"]')?.getAttribute('href')?.match(/^\/track\/([A-Za-z0-9]+)/)?.[1];
  const root=row||(footer&&(!id||id===currentId)?footer:null);
  for(const link of root?.querySelectorAll('a[href^="/artist/"]')||[]){
    const id=link.getAttribute('href')?.match(/^\/artist\/([A-Za-z0-9]{1,64})$/)?.[1];
    const name=link.textContent.trim();if(!id||!name||seen.has(id))continue;seen.add(id);result.push({id,name});}
  return result;
})()'''

ALBUM_REFERENCE=r'''(() => {
  const uri=URI,current=CURRENT;
  const id=uri.match(/(?:spotify:track:|\/track\/)([A-Za-z0-9]{1,64})(?:$|[?/#])/)?.[1];
  if(!id)return null;
  const row=Array.from(document.querySelectorAll('main [data-testid="tracklist-row"]'))
    .find(row=>row.querySelector('a[href="/track/'+id+'"]'));
  const footer=current?document.querySelector('footer, [data-testid="now-playing-widget"]'):null;
  const currentId=footer?.querySelector('a[href^="/track/"]')?.getAttribute('href')?.match(/^\/track\/([A-Za-z0-9]{1,64})(?:$|\?)/)?.[1];
  const root=row||(footer&&currentId===id?footer:null);
  const href=root?.querySelector('a[href^="/album/"]')?.getAttribute('href')||'';
  const album=href.match(/^\/album\/([A-Za-z0-9]{1,64})(?:$|\?)/)?.[1];
  return album?{id:album}:null;
})()'''

READ=r'''(() => {
  const root=document.querySelector('main');if(!root)return null;
  const name=root.querySelector('h1')?.textContent.trim()||'';if(!name)return null;
  const seen=new Set(),releases=[];
  for(const link of root.querySelectorAll('a[href^="/album/"]')){
    const id=link.getAttribute('href')?.match(/^\/album\/([A-Za-z0-9]{1,64})$/)?.[1];
    const card=link.closest('[data-encore-id="card"]');if(!id||!card||seen.has(id))continue;seen.add(id);
    releases.push({id,kind:'album',uri:'spotify:album:'+id,href:'/album/'+id,
      title:card.querySelector('[data-encore-id="cardTitle"]')?.textContent.trim()||link.textContent.trim(),
      subtitle:card.querySelector('[data-encore-id="cardSubtitle"]')?.textContent.trim()||'',image:card.querySelector('img')?.src||''});
    if(releases.length>=100)break;
  }
  const songs=[];
  for(const row of root.querySelectorAll('[data-testid="tracklist-row"]')){
    const link=row.querySelector('a[href^="/track/"]');
    const id=link?.getAttribute('href')?.match(/^\/track\/([A-Za-z0-9]{1,64})$/)?.[1];if(!id)continue;
    const parts=(Array.from(row.querySelectorAll('[data-encore-id="text"]')).map(a=>a.textContent.trim()).find(t=>/^\d+:\d\d$/.test(t))||'').split(':').map(Number);
    songs.push({id,uri:'spotify:track:'+id,kind:'track',title:link.textContent.trim(),
      artist:Array.from(row.querySelectorAll('a[href^="/artist/"]')).map(a=>a.textContent.trim()).join(', '),
      image:row.querySelector('img')?.src||'',duration_ms:parts.length===2?(parts[0]*60+parts[1])*1000:0});
    if(songs.length>=50)break;
  }
  const image=root.querySelector('[data-testid="artist-image"] img, [data-testid="entity-image"] img, [data-testid="entityImage"] img')?.src||'';
  const bio=root.querySelector('[data-testid="artist-about-description"], [data-testid="artist-biography"], [data-testid="artist-about"] p')?.textContent.trim().slice(0,14000)||'';
  const links=Array.from(root.querySelectorAll('a[href]')).map(a=>a.getAttribute('href'))
    .filter(p=>/^\/artist\/[A-Za-z0-9]{1,64}\/discography\/(all|album|single|compilation)$/.test(p));
  return {name,image,bio,releases,songs,links};
})()'''

CHOICES=r'''(() => {
  const seen=new Set(),result=[];
  for(const link of document.querySelectorAll('main a[href^="/artist/"]')){
    const id=link.getAttribute('href')?.match(/^\/artist\/([A-Za-z0-9]{1,64})$/)?.[1];
    const card=link.closest('[data-encore-id="card"]');if(!id||!card||seen.has(id))continue;
    const name=card.querySelector('[data-encore-id="cardTitle"]')?.textContent.trim()||link.textContent.trim();
    if(!name)continue;seen.add(id);result.push({id,name,image:card.querySelector('img')?.src||''});
  }
  return result.slice(0,20);
})()'''


class SpotifyArtist:
    def __init__(self,client):self.client=client

    def navigate(self,path):
        if not re.fullmatch(r'/(artist/[A-Za-z0-9]{1,64}(/discography/(all|album|single|compilation))?|album/[A-Za-z0-9]{1,64})',path):
            raise ValueError('Invalid Spotify music path')
        if not self.client.evaluate(NAVIGATE.replace('PATH',json.dumps(path))):
            raise RuntimeError(text('Spotify navigation is unavailable. Reconnect the desktop client in Accounts.',
                                    'Навигация Spotify недоступна. Переподключи настольный клиент в Аккаунтах.'))
        for _ in range(35):
            if self.client.evaluate('location.pathname==='+json.dumps(path)):
                time.sleep(.4);return
            time.sleep(.15)
        raise RuntimeError(text('Spotify is still loading this page. Retry.', 'Spotify ещё загружает страницу. Повтори попытку.'))

    def read(self):
        best=None
        for _ in range(25):
            best=self.client.evaluate(READ)
            if best and (best.get('songs') or best.get('releases')):break
            time.sleep(.15)
        if not best:raise RuntimeError(text('Spotify did not return this artist.', 'Spotify не передал данные артиста.'))
        for value in best.get('releases',[])+best.get('songs',[]):value['image']=image_url(value.get('image',''))
        return best

    def load(self,category,ref,offset=0):
        ident=str(ref.get('id') or '')
        if ident and not re.fullmatch(r'[A-Za-z0-9]{1,64}',ident):raise ValueError('Invalid Spotify ID')
        if category=='release':
            if not ident:
                album=self.client.evaluate(ALBUM_REFERENCE.replace('URI',json.dumps(str(ref.get('songUri') or '')))
                    .replace('CURRENT','true' if ref.get('current') else 'false')) or {}
                ident=str(album.get('id') or '')
                if not re.fullmatch(r'[A-Za-z0-9]{1,64}',ident):
                    raise RuntimeError(text('Spotify did not supply the album for this recording. Retry while the song is selected.',
                        'Spotify не передал альбом этой записи. Повтори, пока выбрана эта песня.'))
            self.navigate('/album/'+ident)
            data=self.client.tracks({'href':'/album/'+ident})
            info=self.read()
            return {'release':{'id':ident,'kind':'album','uri':'spotify:album:'+ident,
                    'title':data.get('title') or info['name'],'image':image_url(info.get('image','')),
                    'description':info.get('bio','')},'items':data.get('tracks',[]),
                    'note':text('Loaded tracks from the Spotify desktop client','Треки, загруженные настольным клиентом Spotify')}
        if not ident:
            choices=self.client.evaluate(REFERENCES.replace('URI',json.dumps(str(ref.get('songUri') or ''))).replace('CURRENT','true' if ref.get('current') else 'false')) or []
            if len(choices)==1:ident=choices[0]['id']
            elif choices:return {'choices':choices}
            else:
                self.client.search(str(ref.get('name') or '')[:200])
                return {'choices':self.client.evaluate(CHOICES) or []}
        self.navigate('/artist/'+ident);info=self.read()
        if category=='artist-section':
            section=ref.get('section');suffix={'albums':'album','singles':'single','compilations':'compilation'}.get(section)
            path='/artist/'+ident+'/discography/'+str(suffix)
            if suffix and path in info.get('links',[]):
                self.navigate(path);info=self.read();values=info.get('releases',[])
            else:
                patterns={'albums':r'\balbum\b|альбом','singles':r'\bsingle\b|\bep\b|сингл|мини-альбом',
                          'compilations':r'compilation|сборник'}
                values=[v for v in info.get('releases',[]) if re.search(patterns.get(section,r'(?!)'),v.get('subtitle',''),re.I)]
            return {'items':values,'next':None,'note':text('Showing releases exposed by the desktop client; unavailable categories stay empty.',
                'Показаны релизы, доступные в настольном клиенте; непереданные категории остаются пустыми.')}
        return {'artist':{'id':ident,'name':info['name'],'image':image_url(info.get('image','')),'bio':info.get('bio',''),'genres':[]},
                'sections':[{'id':'latest-release','items':info.get('releases',[])},{'id':'top-songs','items':info.get('songs',[])}],
                'note':text('Artist information from the connected Spotify desktop client','Данные артиста из подключённого настольного клиента Spotify')}
