"""Opt-in localhost Quest companion. No credentials or DRM material leave Ember.

Start with EMBERBOX_QUEST=1; use ADB reverse for the headset. HTTP workers never
access GTK directly. Only an explicitly requested audio stream opens a PipeWire
tap of the application's selected source, held in bounded memory, never on disk.
"""
from concurrent.futures import Future,TimeoutError
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json,os,secrets,threading,time,queue,math
from pathlib import Path
from urllib.parse import urlsplit,parse_qs

PORT=8769
SOURCES=('spotify','apple-music','youtube','yandex-music')
FIELDS=('id','uri','title','name','artist','album','image','duration_ms','kind','subtitle','releaseDate','trackCount','playable','artistId','artistUri','description','bio','genres','url','href','catalogId','source','songId','songUri','songKind','current','storefront','section')


def public(value):
    if isinstance(value,list):return [public(v) for v in value[:200]]
    if isinstance(value,dict):return {k:public(v) for k,v in value.items() if k in FIELDS or k in ('items','tracks','artist','release','sections','next','note','total','choices','section')}
    if isinstance(value,str):return value[:24000]
    if value is None or isinstance(value,(int,float,bool)):return value
    return None


class QuestBridge:
    def __init__(self,host,root=None,port=PORT):
        from gi.repository import GLib
        self.metrics={};self.host=host;self.GLib=GLib;self.closed=False;self.tap=None;self.audio_queues=set();self.audio_lock=threading.Lock();self.dj=None;self.lyrics=None;self.karaoke=None;self.youtube_search=None
        self.web_origin=os.environ.get("EMBERBOX_QUEST_ORIGIN","").rstrip("/")
        if self.web_origin and (urlsplit(self.web_origin).scheme!="https" or urlsplit(self.web_origin).path):raise ValueError("Quest origin must be an HTTPS origin")
        self.root=Path(root or os.environ.get('EMBERBOX_QUEST_WEB',Path(__file__).resolve().parents[1]/'quest'/'dist')).resolve()
        if not (self.root/'index.html').is_file():raise RuntimeError('Build Quest web assets first: npm --prefix quest run build')
        from paths import CACHE_DIR
        runtime=Path(os.environ.get('XDG_RUNTIME_DIR',CACHE_DIR))/'emberbox-audio'
        runtime.mkdir(mode=0o700,parents=True,exist_ok=True)
        token_file=runtime/'quest-session-token'
        self.token=''
        try:
            if token_file.stat().st_mode&0o777==0o600 and token_file.stat().st_uid==os.getuid() and token_file.stat().st_size<128:
                self.token=token_file.read_text().strip()
        except OSError:pass
        if len(self.token)<40:
            self.token=secrets.token_urlsafe(32)
            fd=os.open(token_file,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as stream:stream.write(self.token)
            os.chmod(token_file,0o600)
        owner=self
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args):pass
            def send(self,status,value,mime='application/json'):
                raw=json.dumps(value,ensure_ascii=False,allow_nan=False).encode() if mime=='application/json' else value
                self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)))
                self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.end_headers()
                self.wfile.write(raw)
            def end_headers(self):
                origin=self.headers.get('Origin')
                if origin and origin==owner.web_origin:
                    self.send_header('Access-Control-Allow-Origin',origin)
                    self.send_header('Vary','Origin')
                    self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
                    self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type')
                    self.send_header('Access-Control-Allow-Private-Network','true')
                super().end_headers()
            def do_OPTIONS(self):
                if not owner.web_origin or self.headers.get('Origin')!=owner.web_origin:
                    self.send(403,{'error':'Origin not allowed'});return
                self.send(204,b'','text/plain')
            def allowed(self):
                authority=self.headers.get('Host','');origin=self.headers.get('Origin')
                hosts={f'localhost:{owner.port}',f'127.0.0.1:{owner.port}'}
                if authority not in hosts or (origin and origin not in ({'http://'+h for h in hosts}|({owner.web_origin} if owner.web_origin else set()))):return False
                return secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+owner.token)
            def do_GET(self):
                path=urlsplit(self.path)
                try:
                    if path.path.startswith('/api/'):
                        if not self.allowed():self.send(403,{'error':'Pair this headset with Ember first'});return
                        if path.path=='/api/state':self.send(200,owner.call(owner.state));return
                        if path.path=='/api/metrics':self.send(200,owner.metrics);return
                        if path.path=='/api/audio':owner.stream_audio(self);return
                        if path.path=='/api/image':
                            raw,mime=owner.image(parse_qs(path.query).get('url',[''])[0]);self.send(200,raw,mime);return
                        self.send(404,{'error':'Unknown endpoint'});return
                    if self.headers.get('Host','') not in {f'localhost:{owner.port}',f'127.0.0.1:{owner.port}'}:self.send(403,{'error':'Local host only'});return
                    import mimetypes
                    file=(owner.root/path.path.lstrip('/')).resolve() if path.path!='/' else owner.root/'index.html'
                    if not file.is_relative_to(owner.root) or not file.is_file():self.send(404,{'error':'Not found'});return
                    self.send(200,file.read_bytes(),mimetypes.guess_type(file)[0] or 'application/octet-stream')
                except (BrokenPipeError,ConnectionResetError):pass
                except Exception as exc:self.send(502,{'error':str(exc)[:180]})
            def do_POST(self):
                if not self.allowed():self.send(403,{'error':'Not paired'});return
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if size<2 or size>64000:raise ValueError('Invalid request size')
                    data=json.loads(self.rfile.read(size));path=urlsplit(self.path).path
                    if path=='/api/metrics':
                        owner.metrics={k:data[k] for k in ('fps','drawCalls','triangles','mode','audio') if k in data};self.send(200,{'ok':True})
                    elif path=='/api/browse':
                        result=owner.browse(data);self.send(200,result)
                    elif path=='/api/action':self.send(200,owner.call(lambda:owner.action(data)))
                    else:self.send(404,{'error':'Unknown endpoint'})
                except (ValueError,KeyError,TypeError) as exc:self.send(400,{'error':str(exc)[:180]})
                except Exception as exc:self.send(502,{'error':str(exc)[:180]})
        self.server=ThreadingHTTPServer(('127.0.0.1',port),Handler);self.server.daemon_threads=True;self.port=self.server.server_address[1]
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True,name='ember-quest-http');self.thread.start()
        from paths import CACHE_DIR
        runtime=Path(os.environ.get('XDG_RUNTIME_DIR',CACHE_DIR))/'emberbox-audio';runtime.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.pair_file=runtime/'quest-pair.json'
        fd=os.open(self.pair_file,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as stream:json.dump({'url':f'http://localhost:{self.port}/#pair={self.token}','port':self.port},stream)
        os.chmod(self.pair_file,0o600)
        self.timer=GLib.timeout_add(500,self.refresh_target)

    def call(self,callback,timeout=8):
        future=Future()
        def invoke():
            if future.cancelled():return False
            if self.closed:future.set_exception(RuntimeError('Quest companion closed'));return False
            try:future.set_result(callback())
            except Exception as exc:future.set_exception(exc)
            return False
        self.GLib.idle_add(invoke,priority=self.GLib.PRIORITY_DEFAULT)
        try:return future.result(timeout=timeout)
        except TimeoutError:future.cancel();raise

    def state(self):
        from music_library import snapshot
        from artist_catalog import artist_ref,album_ref
        from audio_quality import current as current_quality
        h=self.host;s=snapshot(h)
        s.update(artistRef=public(artist_ref(h)),albumRef=public(album_ref(h)),source=h.source,album=h.album.get_text(),image=h.art_url or '',volume=h.sound.volume,muted=h.sound.muted,
                 levels=list(h.meter.levels),rms=float(getattr(h.meter,'rms_level',0)),flow=h.music.flow.enabled,
                 queue=[public(v) for _,v in h.music.book.upcoming(h.source)[:100]],
                 beat=getattr(h.meter,'beat_grid',None),companion=True,
                 favorite=h.music.favorites.saved(h.music.favorites.current()),
                 audio={'format':'f32le','sampleRate':48000,'channels':2,'sourceOnly':True})
        s['quality']=current_quality(h)
        if self.karaoke:
            a=self.karaoke;s['karaoke']={k:getattr(a,k) for k in ('active','starting','available','engine','amount','phase','error','delay')}
        if self.dj:s['dj']={'busy':self.dj.busy,'phase':self.dj.phase,'reply':self.dj.intro,'error':self.dj.error,'items':public(self.dj.items)}
        if self.lyrics:
            st=self.lyrics.state;s['lyrics']={'status':st.status,'synced':st.synced,'lines':[{'time':v.seconds,'text':v.text} for v in st.lines]}
        return s

    def browse(self,data):
        category=data.get('category','home')
        if category not in ('home','albums','recent','search','artist','artist-section','release','playlist','favorites'):raise ValueError('Unsupported collection')
        if category=='favorites':return self.call(lambda:{'items':public(list(self.host.music.favorites.items.values()))})
        source=self.call(lambda:self.host.source)
        term=str(data.get('term',''))[:200];collection=public(data.get('collection'))
        offset=max(0,min(2000,int(data.get('offset',0))))
        if source=='youtube' and category=='search':
            from youtube_search import Search,video_url
            from music_library import youtube_item
            parsed=video_url(term)
            if parsed:return {'items':[youtube_item({'id':parsed[0].rsplit('=',1)[-1],'title':'YouTube','duration':0})]}
            result=Future()
            def done(items,error):
                if not result.done():
                    if error:result.set_exception(RuntimeError(error))
                    else:result.set_result({'items':[youtube_item(i) for i in items]})
            def begin():
                if self.youtube_search:self.youtube_search.cancel()
                self.youtube_search=Search(done);self.youtube_search.start(term)
            self.call(begin)
            return public(result.result(timeout=42))
        # Independent HTTP worker, sharing the repository lock but never the
        # desktop browse generation. XR paging must not cancel the GTK view.
        return public(self.host.music.repository.load(source,category,term,collection,offset))

    def vocal(self):
        if not self.karaoke:
            from karaoke_audio import KaraokeAudio
            self.karaoke=KaraokeAudio()
        return self.karaoke

    @staticmethod
    def number(value,low,high):
        result=float(value)
        if not math.isfinite(result):raise ValueError('Expected finite number')
        return max(low,min(high,result))

    def action(self,data):
        h=self.host;op=data.get('op');value=data.get('value')
        if op in ('toggle','next','previous'):h.on_action(None,op)
        elif op=='seek':h.seek_to(self.number(value,0,h.length/1e6))
        elif op=='volume':h.sound.set_volume(self.number(value,0,1))
        elif op=='mute':h.sound.toggle_mute()
        elif op=='source':
            if self.karaoke:self.karaoke.disable()
            if value not in SOURCES:raise ValueError('Invalid source')
            h.select_source(value)
        elif op=='play':
            item=public(data['item'])
            source=item.get('source',h.source)
            if source not in SOURCES:raise ValueError('Invalid source')
            if source!=h.source:h.select_source(source)
            h.music.play_now(item,context=public(data.get('context',[])))
        elif op=='queue':h.music.add(public(data['items']))
        elif op=='queue-clear':
            if not h.music.album_listening:h.music.book.clear(h.source);h.music.changed()
        elif op=='flow':h.music.flow.set_enabled(bool(value))
        elif op=='favorite':
            h.music.favorites.set(h.music.favorites.current(),bool(value))
        elif op=='dj':
            if not self.dj:
                from dj_service import DJService
                self.dj=DJService(h.music);self.dj.activate()
            self.dj.ask(str(value)[:500])
        elif op=='karaoke':
            a=self.vocal()
            if value:
                if not a.available:raise ValueError('Install the karaoke model in Ember on PC first')
                a.enable(getattr(h.sound,'target',None))
            else:a.disable()
        elif op=='karaoke-amount':self.vocal().set_amount(self.number(value,0,1))
        elif op=='karaoke-engine':
            if value not in ('ai','stereo'):raise ValueError('Invalid karaoke engine')
            self.vocal().set_engine(value)
        elif op=='lyrics':
            from lyrics import LyricsClient, yandex_recording
            if not self.lyrics:
                self.lyrics=LyricsClient(lambda *_:None)
            self.lyrics.set_track(h.title.get_text(),h.artist.get_text(),h.album.get_text(),h.length/1e6,yandex=yandex_recording(h))
        else:raise ValueError('Unsupported action')
        return {'ok':True}

    def image(self,url):
        from urllib.request import urlopen,Request
        from urllib.parse import urlsplit
        host=(urlsplit(url).hostname or '').lower()
        if urlsplit(url).scheme!='https' or not any(host==v or host.endswith('.'+v) for v in ('scdn.co','mzstatic.com','ytimg.com','yandex.net','yandex.ru')):raise ValueError('Untrusted artwork host')
        # Disable redirect escape: every final URL must still be an artwork CDN.
        class NoRedirect(__import__('urllib.request',fromlist=['HTTPRedirectHandler']).HTTPRedirectHandler):
            def redirect_request(self,*_args):return None
        from urllib.request import build_opener
        with build_opener(NoRedirect).open(Request(url,headers={'User-Agent':'Emberbox-Quest/0.1'}),timeout=8) as response:
            mime=response.headers.get_content_type()
            if mime not in ('image/jpeg','image/png','image/webp'):raise ValueError('Unsupported artwork format')
            raw=response.read(4_000_001)
            if len(raw)>4_000_000:raise ValueError('Artwork exceeds limit')
            return raw,mime

    def refresh_target(self):
        if self.closed:return False
        if self.tap and self.audio_queues and self.tap.target!=self.audio_target():
            self.tap.set_target(self.audio_target());self.tap.start()
        return True

    def audio_target(self):
        if self.karaoke and self.karaoke.active and self.karaoke.process:
            from stream_target import Target
            return Target('karaoke',self.karaoke.process.pid,'','karaoke',True)
        return self.host.meter.target

    def audio_subscribe(self,sink):
        if not self.tap:
            from audio_meter import SpotifyAudioMeter,HOP_BYTES
            owner=self
            class Tap(SpotifyAudioMeter):
                def _measure(self,raw,sample_end=None):
                    with owner.audio_lock:
                        for sink in tuple(owner.audio_queues):
                            try:sink.put_nowait(raw[:HOP_BYTES])
                            except queue.Full:
                                try:sink.get_nowait();sink.put_nowait(raw[:HOP_BYTES])
                                except (queue.Empty,queue.Full):pass
            self.tap=Tap();self.tap.node_name='emberbox-quest-audio-'+secrets.token_hex(6)
        with self.audio_lock:
            if len(self.audio_queues)>=2:raise RuntimeError('Two audio listeners already connected')
            self.audio_queues.add(sink)
        self.tap.set_target(self.audio_target());self.tap.start()

    def stream_audio(self,handler):
        sink=queue.Queue(maxsize=8);self.call(lambda:self.audio_subscribe(sink))
        handler.send_response(200);handler.send_header('Content-Type','application/octet-stream');handler.send_header('Connection','close');handler.send_header('Cache-Control','no-store');handler.end_headers()
        try:
            while not self.closed:
                try:raw=sink.get(timeout=2)
                except queue.Empty:raw=bytes(2048*8)
                handler.wfile.write(raw);handler.wfile.flush()
        except (BrokenPipeError,ConnectionResetError,OSError):pass
        finally:
            with self.audio_lock:self.audio_queues.discard(sink)
            def stop():
                if not self.audio_queues and self.tap:self.tap.stop()
            if not self.closed:
                try:self.call(stop)
                except (TimeoutError,RuntimeError):pass

    def close(self):
        if self.closed:return
        self.closed=True
        if self.timer:self.GLib.source_remove(self.timer);self.timer=0
        if self.tap:self.tap.stop()
        if self.dj:self.dj.close()
        if self.lyrics:self.lyrics.close()
        if self.karaoke:self.karaoke.close()
        if self.youtube_search:self.youtube_search.cancel()
        self.server.shutdown();self.server.server_close()
        try:self.pair_file.unlink(missing_ok=True)
        except OSError:pass


def start_if_enabled(host):
    if os.environ.get('EMBERBOX_QUEST')!='1':return None
    try:return QuestBridge(host)
    except (OSError,RuntimeError) as exc:
        import sys
        print('Quest companion unavailable: '+str(exc),file=sys.stderr)
        return None
