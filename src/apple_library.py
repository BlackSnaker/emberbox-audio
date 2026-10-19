"""Apple Music library rendered by GTK, using a local browser companion."""
import threading
from gi.repository import GLib, Gtk
from discovery_panel import DiscoveryPanel, clear, label
from source_picker import text
from apple_bridge import BridgeUnavailable


class AppleLibraryPanel(DiscoveryPanel):
    def __init__(self, artwork, bridge, play_uri, setup):
        self.bridge = bridge
        self.native = bool(getattr(bridge, 'native', False))
        self.setup = setup
        self.category = 'playlists'
        self.pages = {}
        self.next_offset = None
        self.collection_label = 'Apple Music'
        super().__init__(artwork, play_uri, setup)
        self.data = None
        self.reconnect.set_label(text('Sign in to Apple Music', 'Войти в Apple Music') if self.native else text('Connect Firefox companion', 'Подключить Firefox'))
        self.catalog_entry = Gtk.SearchEntry()
        self.catalog_entry.set_no_show_all(True)
        self.catalog_entry.set_placeholder_text(text('Find songs in Apple Music · Enter','Найти треки в Apple Music · Enter'))
        self.catalog_entry.get_style_context().add_class('track-search')
        self.catalog_entry.set_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY,None)
        self.catalog_entry.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY,None)
        self.catalog_entry.connect('activate',lambda _entry:self.load_search())
        self.pack_start(self.catalog_entry,False,False,0)
        self.reorder_child(self.catalog_entry,2)
        self.show_home()

    def show_home(self):
        self.generation += 1
        self.selected = None
        self.track_buttons = []
        self.track_data = None
        self.back.hide()
        self.search.hide()
        self.context_header.hide()
        self.filters_scroll.show()
        self.heading.set_text(text('Your library', 'Твоя медиатека'))
        self.caption.set_text('Apple Music')
        self.notice.set_text('')
        self.busy = False
        self.spinner.stop()
        if hasattr(self,'catalog_entry'):
            self.catalog_entry.set_visible(self.native and self.category == 'search')
        self.render_filters()
        self.render_page()
        GLib.idle_add(self.layout_changed)

    def render_filters(self):
        self._updating_filters = True
        clear(self.filters)
        categories = [('playlists',text('Playlists','Плейлисты')),
                      ('albums',text('Albums','Альбомы')),('songs',text('Songs','Треки'))]
        if self.native:
            categories.append(('search',text('Search','Поиск')))
        for key, name in categories:
            button = Gtk.ToggleButton(label=name)
            button.get_style_context().add_class('filter-chip')
            button.set_active(key == self.category)
            button.connect('clicked', self.select_shelf, key)
            self.filters.pack_start(button, False, False, 0)
        self._updating_filters = False
        self.filters.show_all()

    def select_shelf(self, _button, category):
        if self._updating_filters or self.category == category:
            return
        self.category = category
        self.show_home()
        self.load_home()

    def _request(self, work, finish):
        self.generation += 1
        generation = self.generation
        self.busy = True
        self.spinner.start()
        self.notice.set_text(text('Loading Apple Music…','Загружаю Apple Music…'))
        self.reconnect.hide()
        def run():
            try:
                result, error = work(), None
            except Exception as exc:
                result, error = None, exc
            GLib.idle_add(done, result, error)
        def done(result, error):
            if generation != self.generation:
                return False
            self.busy = False
            self.spinner.stop()
            if error:
                print(f'Apple Music library: {error}', flush=True)
                self.notice.set_text(str(error))
                if not self.bridge.connected:
                    self.notice.set_text(text('Connecting Apple Music…','Подключаю Apple Music…') if self.native else
                                         text('Connect Firefox to show your library here.','Подключи Firefox — медиатека появится здесь.'))
                    self.reconnect.show()
                elif self.native and not getattr(self.bridge, 'state', {}).get('authorized'):
                    self.reconnect.show()
                GLib.idle_add(self.layout_changed)
            else:
                self.notice.set_text('')
                self.reconnect.hide()
                finish(result)
            return False
        threading.Thread(target=run,daemon=True,name='apple-library').start()

    def open(self):
        if not self.selected:
            self.load_home()

    def load_home(self, append=False):
        if self.category == 'search':
            if hasattr(self,'catalog_entry') and self.catalog_entry.get_text().strip():
                self.load_search()
            return
        category = self.category
        offset = self.next_offset if append else 0
        def finish(result):
            items = result.get('items', [])
            old = self.pages.get(category, {}).get('items', []) if append else []
            self.pages[category] = {'items':old+items,'next':result.get('next')}
            print(f'Apple Music library: {len(old+items)} {category}', flush=True)
            self.render_page()
        self._request(lambda:self.bridge.request('browse',category=category,offset=offset or 0),finish)

    def load_search(self):
        if not self.native or self.category != 'search':
            return
        term = self.catalog_entry.get_text().strip()
        if not term:
            return
        def finish(result):
            self.pages['search'] = {'items':result.get('items',[]),'next':None}
            self.render_page()
        self._request(lambda:self.bridge.request('search',term=term),finish)

    def render_page(self):
        clear(self.content)
        self.track_buttons = []
        page = self.pages.get(self.category)
        if page is None:
            title = label(text('Search Apple Music','Поиск в Apple Music') if self.category == 'search' else text('Your music, inside Emberbox','Твоя музыка внутри плеера'),'drawer-heading')
            title.set_margin_top(45)
            self.content.pack_start(title,False,False,0)
            self.content.pack_start(label(text('Playlists, albums and songs from Apple Music.',
                                              'Плейлисты, альбомы и треки из Apple Music.') if self.native else
                                          text('Connect the Firefox companion to load your library.',
                                              'Подключи модуль Firefox для загрузки медиатеки.'),'caption'),False,False,0)
            self.reconnect.set_visible(not self.bridge.connected or (self.native and not getattr(self.bridge,'state',{}).get('authorized')))
            self.content.show_all()
            return
        items = page['items']
        self.next_offset = page.get('next')
        self.search.show()
        self.search.set_placeholder_text(text('Search loaded items','Поиск в загруженных'))
        self.search.set_text('')
        if self.category in ('songs','search'):
            self.selected = {'title':text('Songs','Треки'),'subtitle':'Apple Music',
                             'uri':items[0]['uri'] if items else '', 'image':''}
            # Shared rows retain the same tactile layout and click behaviour.
            super().render_tracks({'tracks':items, 'total':len(items)})
            self.selected = None
            self.context_header.hide()
            self.caption.set_text(text('Apple Music search results','Результаты поиска Apple Music') if self.category == 'search' else text('Songs in your Apple Music library','Треки в твоей медиатеке Apple Music'))
            if self.category == 'search':
                self.search.hide()
        else:
            grid = Gtk.Grid(column_spacing=8,row_spacing=8,column_homogeneous=True)
            self.content.pack_start(grid,False,False,0)
            for n,item in enumerate(items):
                button = Gtk.Button()
                button.get_style_context().add_class('mix-tile')
                row = Gtk.Box(spacing=8)
                image = Gtk.Image()
                self.artwork.load(image,item.get('image',''),50,8)
                row.pack_start(image,False,False,0)
                info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4)
                info.pack_start(label(item['title'],'mix-title',15),False,False,0)
                info.pack_start(label(item.get('subtitle',''),'mix-subtitle',15),False,False,0)
                row.pack_start(info,True,True,0)
                button.add(row)
                button.connect('clicked',self.select_collection,item)
                grid.attach(button,n%2,n//2,1,1)
                self.track_buttons.append((button,{'title':item['title'],'artist':item.get('subtitle',''),'uri':item['uri']}))
        if not items:
            self.content.pack_start(label(text('Nothing here yet','Пока здесь пусто'),'caption'),False,False,10)
        self.add_more(lambda:self.load_home(append=True))
        self.content.show_all()
        self.reconnect.hide()
        GLib.idle_add(self.layout_changed)

    def add_more(self, callback):
        if self.next_offset is not None:
            button = Gtk.Button(label=text('Load more','Загрузить ещё'))
            button.get_style_context().add_class('filter-chip')
            button.connect('clicked',lambda _b:callback() if not self.busy else None)
            self.content.pack_start(button,False,False,5)

    def select_collection(self, _button, item, append=False):
        self.catalog_entry.hide()
        self.selected = item
        self.heading.set_text(item['title'])
        self.caption.set_text('Apple Music')
        self.back.show()
        self.filters_scroll.hide()
        self.search.hide()
        if not append:
            clear(self.content)
        offset = self.next_offset if append else 0
        def finish(result):
            tracks = (self.track_data.get('tracks',[]) if append and self.track_data else [])+result.get('tracks',[])
            self.next_offset = result.get('next')
            super(AppleLibraryPanel,self).render_tracks({'tracks':tracks,'total':len(tracks)})
            self.caption.set_text(f'{len(tracks)} '+text('tracks · Apple Music','треков · Apple Music'))
            self.add_more(lambda:self.select_collection(None,item,append=True))
            self.content.show_all()
        self._request(lambda:self.bridge.request('tracks',kind=item['kind'],id=item['id'],offset=offset or 0),finish)

    def on_refresh(self, _button):
        if self.selected:
            self.select_collection(None,self.selected)
        else:
            self.load_home()

    def on_connect(self, _button):
        self.setup()
