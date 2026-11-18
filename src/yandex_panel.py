"""Warm in-widget My Wave controls and Yandex Music track lists."""
from concurrent.futures import ThreadPoolExecutor
from gi.repository import Gtk,GLib,Pango
from discovery_panel import label,clear
from source_picker import text


class YandexPanel(Gtk.Box):
    def __init__(self,artwork,player,wave,setup,changed):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=9)
        self.artwork,self.player,self.wave,self.setup=artwork,player,wave,setup
        self.play_tracks=None
        self.layout_changed=changed
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='yandex-library')
        self.closed=False;self.generation=0;self.category='collection';self.track_buttons=[]
        self.opened=False;self.initial_requested=False;self.playlist_id=''
        self.set_margin_start(18);self.set_margin_end(18);self.set_margin_bottom(17)
        card=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=7)
        card.get_style_context().add_class('account-card')
        card.pack_start(label(text('Your own wavelength','На твоей волне'),'drawer-heading'),False,False,0)
        card.pack_start(label(text('A personal stream that learns from your likes and skips.',
            'Личный поток, который учится на твоих лайках и пропусках.'),'caption'),False,False,0)
        self.wave_button=Gtk.Button(label=text('≈  Play My Wave','≈  Включить Мою волну'))
        self.wave_button.get_style_context().add_class('warm-button')
        self.wave_button.connect('clicked',lambda _b:self.wave())
        card.pack_start(self.wave_button,False,False,0)
        self.wave_status=label('','caption');self.wave_status.set_line_wrap(True)
        self.wave_status.set_no_show_all(True)
        card.pack_start(self.wave_status,False,False,0)
        self.track_wave_button=Gtk.Button(label=text('≈  Wave from current track','≈  Волна по текущему треку'))
        self.track_wave_button.get_style_context().add_class('filter-chip')
        self.track_wave_button.connect('clicked',lambda _b:self.start_track_wave())
        card.pack_start(self.track_wave_button,False,False,0)
        self.playlist_wave=Gtk.Button(label=text('≈  Wave from playlist','≈  Волна по плейлисту'))
        self.playlist_wave.get_style_context().add_class('filter-chip')
        self.playlist_wave.connect('clicked',lambda _b:self.start_playlist_wave())
        card.pack_start(self.playlist_wave,False,False,0)
        feedback=Gtk.Box(spacing=7)
        for action,title in [('like',text('♡  Like','♡  Нравится')),('dislike',text('⊘  Less like this','⊘  Не моё'))]:
            b=Gtk.Button(label=title);b.get_style_context().add_class('filter-chip')
            b.connect('clicked',lambda _b,a=action:self.request('feedback',action=a))
            feedback.pack_start(b,True,True,0)
        card.pack_start(feedback,False,False,0)
        self.pack_start(card,False,False,0)
        self.entry=Gtk.SearchEntry()
        self.entry.set_placeholder_text(text('Find music in Yandex · Enter','Поиск в Яндекс Музыке · Enter'))
        for position in (Gtk.EntryIconPosition.PRIMARY,Gtk.EntryIconPosition.SECONDARY):self.entry.set_icon_tooltip_text(position,None)
        self.entry.get_style_context().add_class('track-search')
        self.entry.connect('activate',lambda _e:self.search())
        self.pack_start(self.entry,False,False,0)
        filters=Gtk.Box(spacing=7)
        self.playlist_category='personal'
        for category,title in [('personal',text('For you','Для тебя')),('collection',text('Playlists','Плейлисты')),('queue',text('Queue','Очередь'))]:
            b=Gtk.Button(label=title);b.get_style_context().add_class('filter-chip')
            b.connect('clicked',lambda _b,c=category:self.browse(c));filters.pack_start(b,True,True,0)
        self.pack_start(filters,False,False,0)
        self.back=Gtk.Button(label=text('‹  All playlists','‹  Все плейлисты'))
        self.back.get_style_context().add_class('filter-chip')
        self.back.set_no_show_all(True);self.back.connect('clicked',lambda _b:self.browse(self.playlist_category))
        self.pack_start(self.back,False,False,0)
        self.spinner=Gtk.Spinner();self.spinner.set_no_show_all(True);self.pack_start(self.spinner,False,False,0)
        self.scroll=Gtk.ScrolledWindow();self.scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_min_content_height(0);self.scroll.set_max_content_height(250);self.scroll.set_propagate_natural_height(True)
        self.content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5);self.scroll.add(self.content)
        self.pack_start(self.scroll,True,True,0)
        self.notice=label('','caption');self.notice.set_line_wrap(True);self.pack_start(self.notice,False,False,0)
        self.connect_button=Gtk.Button(label=text('Connect Yandex Music','Подключить Яндекс Музыку'))
        self.connect_button.get_style_context().add_class('filter-chip')
        self.connect_button.connect('clicked',lambda _b:self.setup());self.pack_start(self.connect_button,False,False,0)
        self.show_all();self.update()

    def update(self):
        self.update_current(self.player.state.get('id'))
        ready=bool(self.player.connected and self.player.state.get('authorized') and self.player.state.get('ready'))
        self.connect_button.set_visible(not ready)
        if self.player.state.get('regionBlocked'):
            self.notice.set_text(text('Yandex Music is unavailable in this region.','Яндекс Музыка недоступна в этом регионе.'))
        elif self.player.state.get('subscribed') is False:
            self.notice.set_text(text('My Wave requires Yandex Plus. Connect an account with a subscription.',
                'Для Моей волны нужен Яндекс Плюс. Подключи аккаунт с подпиской.'))
        elif not ready:
            self.notice.set_text(self.player.error or text('Sign in to Yandex Music by code in Accounts.',
                'Войди в Яндекс Музыку по коду в разделе аккаунтов.'))
        if not self.player.connected:self.initial_requested=False
        elif self.opened and not self.initial_requested:
            self.initial_requested=True;self.browse('personal')
        state=self.player.state
        self.wave_status.set_text(wave_description(state))
        self.wave_status.set_visible(bool(state.get('wave')))
        self.track_wave_button.set_sensitive(bool(ready and state.get('id')))
        self.track_wave_button.set_tooltip_text(str(state.get('title') or ''))
        context=self.playlist_context()
        self.playlist_wave.set_sensitive(bool(ready and context))
        self.playlist_wave.set_tooltip_text(str((context or {}).get('title') or (context or {}).get('id') or text('Open a playlist first','Сначала открой плейлист')))
        personal=state.get('wave') and state.get('waveKind','personal')=='personal'
        self.wave_button.set_label(text('≈  My Wave is playing','≈  Моя волна играет') if personal and state.get('playing') else text('≈  Play My Wave','≈  Включить Мою волну'))

    def playlist_context(self):
        selected={'kind':'playlist','id':self.playlist_id} if self.category=='tracks' and self.playlist_id else None
        return playlist_wave_context(self.player.state,selected)

    def start_playlist_wave(self):
        context=self.playlist_context()
        if context:self.request('wave',id=context['id'],title=context.get('title',''))

    def start_track_wave(self):
        state=dict(self.player.state)
        if state.get('id'):
            self.request('wave',trackId=str(state['id']),title=str(state.get('title') or ''))

    def open(self):self.opened=True;self.update()
    def on_refresh(self,_button):
        self.update()
        if self.category in ('personal','collection','queue'):self.browse(self.category)
        elif self.category=='search':self.search()
        elif self.category=='tracks':self.open_playlist(self.playlist_id)

    def search(self):
        term=self.entry.get_text().strip()
        if term:
            self.category='search';self.back.hide()
            self.request('search',term=term)

    def browse(self,category):
        self.category=category;self.back.hide()
        self.request('browse',category=category)

    def open_playlist(self,identifier):
        if self.category in ('personal','collection'):self.playlist_category=self.category
        self.category='tracks';self.playlist_id=identifier;self.back.show()
        self.request('tracks',id=identifier)

    def request(self,method,**params):
        if self.closed:return
        if method in ('play','wave'):getattr(self,'before_play',lambda:None)()
        self.generation+=1;generation=self.generation
        self.spinner.show();self.spinner.start()
        self.notice.set_text(text('Connecting your music…','Подключаю твою музыку…'))
        future=self.pool.submit(self.player.request,method,**params)
        def done(item):
            if self.closed or generation!=self.generation:return False
            self.spinner.stop();self.spinner.hide()
            try:
                result=item.result();self.notice.set_text('')
                if method in ('browse','search','tracks'):
                    self.render(result.get('items',[]))
                    if result.get('note'):self.notice.set_text(result['note'])
            except Exception as error:self.notice.set_text(str(error))
            self.layout_changed();return False
        future.add_done_callback(lambda item:GLib.idle_add(done,item))

    def update_current(self,ident):
        for button,track_id in getattr(self,'track_rows',[]):
            style=button.get_style_context()
            if str(ident or '')==track_id:style.add_class('current-track')
            else:style.remove_class('current-track')

    def render(self,items):
        clear(self.content);self.track_buttons=[];self.track_rows=[]
        context=tuple(dict(item,uri=item.get('uri') or 'yandex:track:'+str(item.get('id','')))
                      for item in items if item.get('kind')!='playlist')
        for item in items:
            b=Gtk.Button();b.get_style_context().add_class('track-row')
            row=Gtk.Box(spacing=9);image=Gtk.Image();self.artwork.load(image,item.get('image',''),42,7)
            row.pack_start(image,False,False,0)
            names=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3)
            names.pack_start(label(str(item.get('title','')),'track-title',30),False,False,0)
            names.pack_start(label(text('Playlist · Open','Плейлист · Открыть') if item.get('kind')=='playlist' else str(item.get('artist','')),'caption',35),False,False,0)
            row.pack_start(names,True,True,0);b.add(row)
            if item.get('kind')=='playlist':b.connect('clicked',lambda _b,i=item['id']:self.open_playlist(i))
            else:
                b.connect('clicked',lambda _b,i=item['id'],values=context:self.play_track(i,values))
                self.track_rows.append((b,str(item['id'])))
            self.content.pack_start(b,False,False,0);self.track_buttons.append(b)
        self.content.show_all()
        self.update_current(self.player.state.get('id'))
        if not items:self.notice.set_text(text('No loaded playlists here yet.','Здесь пока нет загруженных плейлистов.') if self.category=='collection' else text('No loaded tracks here yet.','Здесь пока нет загруженных треков.'))

    def play_track(self,identifier,context):
        item=next((value for value in context if str(value.get('id'))==str(identifier)),None)
        if self.play_tracks and item:self.play_tracks(item,context)
        else:self.request('play',id=identifier)

    def close(self):
        self.closed=True;self.generation+=1;self.pool.shutdown(wait=False,cancel_futures=True)


def wave_description(state):
    if not state.get('wave'):return ''
    kind=state.get('waveKind','personal')
    title={'playlist':text('Wave from playlist','Волна по плейлисту'),
           'track':text('Wave from track','Волна по треку')}.get(kind,text('My Wave','Моя волна'))
    if state.get('waveTitle'):title+=' — '+str(state['waveTitle'])
    return '≈  '+title+' · '+(text('Playing','Играет') if state.get('playing') else text('Paused','Пауза'))


def playlist_wave_context(state,selected=None):
    if selected and selected.get('kind')=='playlist' and selected.get('id'):
        return dict(selected)
    if state.get('wave') and state.get('waveKind')=='playlist' and state.get('waveId'):
        return {'id':str(state['waveId']),'title':str(state.get('waveTitle') or '')}
    if state.get('playlistId'):return {'id':str(state['playlistId'])}
    return None
