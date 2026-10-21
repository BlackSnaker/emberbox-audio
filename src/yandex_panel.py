"""Warm in-widget My Wave controls and Yandex Music track lists."""
from concurrent.futures import ThreadPoolExecutor
from gi.repository import Gtk,GLib,Pango
from discovery_panel import label,clear
from source_picker import text


class YandexPanel(Gtk.Box):
    def __init__(self,artwork,player,wave,setup,changed):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=9)
        self.artwork,self.player,self.wave,self.setup=artwork,player,wave,setup
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
        for category,title in [('collection',text('Playlists','Плейлисты')),('queue',text('Queue','Очередь'))]:
            b=Gtk.Button(label=title);b.get_style_context().add_class('filter-chip')
            b.connect('clicked',lambda _b,c=category:self.browse(c));filters.pack_start(b,True,True,0)
        self.pack_start(filters,False,False,0)
        self.back=Gtk.Button(label=text('‹  All playlists','‹  Все плейлисты'))
        self.back.get_style_context().add_class('filter-chip')
        self.back.set_no_show_all(True);self.back.connect('clicked',lambda _b:self.browse('collection'))
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
        ready=bool(self.player.connected and self.player.state.get('authorized') and self.player.state.get('ready'))
        self.connect_button.set_visible(not ready)
        if self.player.state.get('regionBlocked'):
            self.notice.set_text(text('Yandex Music is unavailable in this region.','Яндекс Музыка недоступна в этом регионе.'))
        elif self.player.state.get('subscribed') is False:
            self.notice.set_text(text('My Wave requires Yandex Plus. Connect an account with a subscription.',
                'Для Моей волны нужен Яндекс Плюс. Подключи аккаунт с подпиской.'))
        elif not ready:
            self.notice.set_text(text('The site player is loading. Open its window from Accounts if this persists.',
                'Плеер сайта загружается. Если это не проходит, открой его окно через Аккаунты.') if self.player.connected and self.player.state.get('authorized') else
                text('Sign in with Yandex ID in Accounts.','Войди в Яндекс ID в разделе аккаунтов.'))
        if not self.player.connected:self.initial_requested=False
        elif self.opened and not self.initial_requested:
            self.initial_requested=True;self.browse('collection')
        self.wave_button.set_label(text('≈  My Wave is playing','≈  Моя волна играет') if self.player.state.get('wave') and self.player.state.get('playing') else text('≈  Play My Wave','≈  Включить Мою волну'))

    def open(self):self.opened=True;self.update()
    def on_refresh(self,_button):
        self.update()
        if self.category in ('collection','queue'):self.browse(self.category)
        elif self.category=='search':self.search()
        elif self.category=='tracks':self.open_playlist(self.playlist_id)

    def search(self):
        term=self.entry.get_text().strip()
        if term:self.category='search';self.request('search',term=term)

    def browse(self,category):
        self.category=category;self.back.hide();self.request('browse',category=category)

    def open_playlist(self,identifier):
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
                if method in ('browse','search','tracks'):self.render(result.get('items',[]))
            except Exception as error:self.notice.set_text(str(error))
            self.layout_changed();return False
        future.add_done_callback(lambda item:GLib.idle_add(done,item))

    def render(self,items):
        clear(self.content);self.track_buttons=[]
        for item in items[:50]:
            b=Gtk.Button();b.get_style_context().add_class('track-row')
            row=Gtk.Box(spacing=9);image=Gtk.Image();self.artwork.load(image,item.get('image',''),42,7)
            row.pack_start(image,False,False,0)
            names=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3)
            names.pack_start(label(str(item.get('title','')),'track-title',30),False,False,0)
            names.pack_start(label(text('Playlist · Open','Плейлист · Открыть') if item.get('kind')=='playlist' else str(item.get('artist','')),'caption',35),False,False,0)
            row.pack_start(names,True,True,0);b.add(row)
            if item.get('kind')=='playlist':b.connect('clicked',lambda _b,i=item['id']:self.open_playlist(i))
            else:b.connect('clicked',lambda _b,i=item['id']:self.request('play',id=i))
            self.content.pack_start(b,False,False,0);self.track_buttons.append(b)
        self.content.show_all()
        if not items:self.notice.set_text(text('No loaded playlists here yet.','Здесь пока нет загруженных плейлистов.') if self.category=='collection' else text('No loaded tracks here yet.','Здесь пока нет загруженных треков.'))

    def close(self):
        self.closed=True;self.generation+=1;self.pool.shutdown(wait=False,cancel_futures=True)
