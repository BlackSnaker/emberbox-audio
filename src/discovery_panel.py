"""Personal Spotify shelves and their actual tracks inside the desktop card."""

import threading
import time

from gi.repository import GLib, Gtk, Pango

from discovery import ConnectionUnavailable, LocalSpotify, cached_home


def label(text, style, width=None):
    widget = Gtk.Label(label=text)
    widget.set_xalign(0)
    widget.get_style_context().add_class(style)
    if width:
        widget.set_max_width_chars(width)
        widget.set_ellipsize(Pango.EllipsizeMode.END)
    return widget


def clear(container):
    for child in container.get_children():
        child.destroy()


class DiscoveryPanel(Gtk.Box):
    def __init__(self, artwork, play_uri, connect_spotify, client_factory=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.artwork = artwork
        self.client_factory=client_factory or LocalSpotify
        self.play_uri = play_uri
        self.play_tracks = None
        self.connect_spotify = connect_spotify
        self.data = None if client_factory else cached_home()
        self.selected = None
        self.track_data = None
        self.generation = 0
        self.current_uri = ''
        self.track_buttons = []
        self.busy = False
        self._updating_filters = False
        self._active_shelf = None
        self.layout_changed = lambda: False
        self.loaded_at = 0
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_bottom(17)

        heading = Gtk.Box(spacing=7)
        self.back = Gtk.Button(label='‹')
        self.back.get_style_context().add_class('mini-button')
        self.back.connect('clicked', lambda _b: self.show_home())
        self.back.get_accessible().set_name('Back to collections')
        heading.pack_start(self.back, False, False, 0)
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.heading = label('Made for you', 'drawer-heading', 30)
        self.caption = label('Your personal Spotify picks', 'caption', 45)
        titles.pack_start(self.heading, False, False, 0)
        titles.pack_start(self.caption, False, False, 0)
        heading.pack_start(titles, True, True, 0)
        self.spinner = Gtk.Spinner()
        heading.pack_start(self.spinner, False, False, 0)
        refresh = Gtk.Button(label='↻')
        refresh.get_style_context().add_class('mini-button')
        refresh.get_accessible().set_name('Refresh from Spotify')
        refresh.connect('clicked', self.on_refresh)
        heading.pack_end(refresh, False, False, 0)
        self.pack_start(heading, False, False, 0)

        self.filters_scroll = Gtk.ScrolledWindow()
        self.filters_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.filters_scroll.set_min_content_height(34)
        self.filters_scroll.get_style_context().add_class('filter-scroll')
        self.filters = Gtk.Box(spacing=5)
        self.filters_scroll.add(self.filters)
        self.pack_start(self.filters_scroll, False, False, 0)

        self.context_header = Gtk.Box(spacing=10)
        self.pack_start(self.context_header, False, False, 0)
        self.search = Gtk.SearchEntry()
        self.search.set_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY, None)
        self.search.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, None)
        self.search.set_placeholder_text('Search this collection')
        self.search.get_style_context().add_class('track-search')
        self.search.connect('search-changed', self.filter_tracks)
        self.pack_start(self.search, False, False, 0)

        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_min_content_height(302)
        self.scroll.set_max_content_height(302)
        self.scroll.set_propagate_natural_height(False)
        self.scroll.get_style_context().add_class('discovery-scroll')
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.scroll.add(self.content)
        self.pack_start(self.scroll, True, True, 0)

        self.notice = label('', 'caption', 55)
        self.notice.set_line_wrap(True)
        self.notice.set_max_width_chars(54)
        self.pack_start(self.notice, False, False, 0)
        self.reconnect = Gtk.Button(label='Connect Spotify')
        self.reconnect.get_style_context().add_class('warm-button')
        self.reconnect.connect('clicked', self.on_connect)
        self.pack_start(self.reconnect, False, False, 0)
        self.show_all()
        self.show_home()

    def open(self):
        if not self.selected and not self.busy and (not self.data or time.time() - self.loaded_at > 600):
            self.load_home()

    def show_home(self):
        self.generation += 1
        self.selected = None
        self.track_data = None
        self.track_buttons = []
        self.back.hide()
        self.search.hide()
        self.context_header.hide()
        self.filters_scroll.show()
        self.reconnect.hide()
        self.heading.set_text('Made for you')
        self.caption.set_text('Your personal Spotify picks')
        self.notice.set_text('')
        self.busy = False
        self.spinner.stop()
        self.render_filters()
        GLib.idle_add(self.layout_changed)

    def render_filters(self):
        self._active_shelf = None
        clear(self.filters)
        shelves = (self.data or {}).get('shelves', [])
        names = {'Миксы дня и открытия': 'Для тебя', 'Рекомендуемые станции': 'Радио',
                 'Твои лучшие миксы': 'Миксы', 'Новые релизы для тебя': 'Новинки',
                 'Альбомы с треками, которые тебе нравятся': 'Альбомы',
                 'Слушаем дальше?': 'Продолжить', 'Soundtrack your Sunday morning': 'Настроение'}
        for index, shelf in enumerate(shelves):
            button = Gtk.ToggleButton(label=names.get(shelf['title'], shelf['title']))
            button.get_style_context().add_class('filter-chip')
            button.connect('clicked', self.select_shelf, index)
            self.filters.pack_start(button, False, False, 0)
        self.filters.show_all()
        if shelves:
            self.select_shelf(self.filters.get_children()[0], 0)
        else:
            clear(self.content)
            empty = label('Your next favourite starts here', 'drawer-heading')
            empty.set_margin_top(75)
            empty.set_halign(Gtk.Align.CENTER)
            self.content.pack_start(empty, False, False, 0)
            sub = label('Your mixes, discoveries and tracks appear here', 'caption')
            sub.set_halign(Gtk.Align.CENTER)
            self.content.pack_start(sub, False, False, 0)
            self.content.show_all()

    def select_shelf(self, _button, index):
        shelves = (self.data or {}).get('shelves', [])
        if self._updating_filters or not 0 <= index < len(shelves):
            return
        # GtkToggleButton.set_active() also emits "clicked". Those callbacks
        # must not start another selection while we synchronize the chips.
        self._updating_filters = True
        try:
            for n, chip in enumerate(self.filters.get_children()):
                chip.set_active(n == index)
        finally:
            self._updating_filters = False
        if self._active_shelf == index:
            return
        self._active_shelf = index
        shelf = shelves[index]
        clear(self.content)
        grid = Gtk.Grid(column_spacing=8, row_spacing=8, column_homogeneous=True)
        self.content.pack_start(grid, False, False, 0)
        for n, item in enumerate(shelf['items']):
            button = Gtk.Button()
            button.get_style_context().add_class('mix-tile')
            button.get_accessible().set_name(item['title'] + '\n' + item.get('subtitle', ''))
            row = Gtk.Box(spacing=9)
            image = Gtk.Image()
            self.artwork.load(image, item.get('image', ''), 56, 9)
            row.pack_start(image, False, False, 0)
            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            title = label(item['title'], 'mix-title', 15)
            title.set_line_wrap(True)
            title.set_lines(2)
            info.pack_start(title, False, False, 0)
            subtitle = label(item.get('subtitle', ''), 'mix-subtitle', 15)
            info.pack_start(subtitle, False, False, 0)
            info.set_valign(Gtk.Align.CENTER)
            row.pack_start(info, True, True, 0)
            button.add(row)
            button.connect('clicked', self.select_collection, item)
            grid.attach(button, n % 2, n // 2, 1, 1)
        self.content.show_all()
        self.scroll.get_vadjustment().set_value(0)

    def _request(self, work, finish):
        self.generation += 1
        generation = self.generation
        self.busy = True
        self.spinner.start()
        self.notice.set_text('Loading from Spotify…')
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
                self.notice.set_text(str(error) or 'Could not refresh Spotify.')
                if isinstance(error, ConnectionUnavailable):
                    self.reconnect.show()
                GLib.idle_add(self.layout_changed)
                return False
            self.notice.set_text('')
            finish(result)
            return False

        threading.Thread(target=run, name='spotify-discovery', daemon=True).start()

    def load_home(self):
        def work():
            with self.client_factory() as spotify:
                return spotify.home()

        def finish(result):
            self.data = result
            self.loaded_at = time.time()
            self.show_home()

        self._request(work, finish)

    def select_collection(self, _button, item):
        self.selected = item
        self.track_buttons = []
        self.heading.set_text(item['title'])
        self.caption.set_text('Tracks from your collection')
        self.back.show()
        self.filters_scroll.hide()
        self.search.hide()
        self.context_header.hide()
        clear(self.content)

        def work():
            with self.client_factory() as spotify:
                return spotify.tracks(item)

        self._request(work, self.render_tracks)

    def render_tracks(self, data):
        self.track_data = data
        self.caption.set_text(f"{data.get('total', len(data['tracks']))} tracks · Your Spotify collection")
        clear(self.context_header)
        image = Gtk.Image()
        self.artwork.load(image, self.selected.get('image', ''), 42, 8)
        self.context_header.pack_start(image, False, False, 0)
        description = label(self.selected.get('subtitle', ''), 'mix-subtitle', 30)
        description.set_line_wrap(True)
        description.set_lines(2)
        self.context_header.pack_start(description, True, True, 0)
        play = Gtk.Button(label='▶  Play')
        play.get_style_context().add_class('warm-button')
        play.connect('clicked', lambda _b: self.play_uri(self.selected['uri']))
        self.context_header.pack_end(play, False, False, 0)
        self.context_header.show_all()
        self.search.set_text('')
        self.search.show()
        clear(self.content)
        self.track_buttons = []
        for n, track in enumerate(data['tracks']):
            button = Gtk.Button()
            button.get_style_context().add_class('track-row')
            row = Gtk.Box(spacing=8)
            number = label(f'{n + 1:02}', 'track-number')
            number.set_size_request(20, -1)
            row.pack_start(number, False, False, 0)
            image = Gtk.Image()
            self.artwork.load(image, track.get('image', ''), 34, 6)
            row.pack_start(image, False, False, 0)
            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            info.pack_start(label(track['title'], 'track-title', 34), False, False, 0)
            info.pack_start(label(track.get('artist', ''), 'mix-subtitle', 36), False, False, 0)
            row.pack_start(info, True, True, 0)
            seconds = int(track.get('duration_ms', 0) / 1000)
            duration = label(f'{seconds // 60}:{seconds % 60:02d}', 'track-duration')
            row.pack_end(duration, False, False, 0)
            button.add(row)
            button.get_accessible().set_name(track['title'] + '\n' + track.get('artist', ''))
            button.set_sensitive(track.get('playable', True))
            button.connect('clicked', lambda _b, item=track: self.play_track(item))
            self.content.pack_start(button, False, False, 0)
            self.track_buttons.append((button, track))
        self.content.show_all()
        self.update_current(self.current_uri)
        self.scroll.get_vadjustment().set_value(0)
        if len(data['tracks']) < data.get('total', 0):
            self.notice.set_text(f"Showing the first {len(data['tracks'])} tracks")
        GLib.idle_add(self.layout_changed)

    def play_track(self,item):
        if self.play_tracks:
            self.play_tracks(item,[value for button,value in self.track_buttons if button.get_visible()])
        else:self.play_uri(item['uri'])

    def filter_tracks(self, entry):
        query = entry.get_text().strip().casefold()
        for button, track in self.track_buttons:
            haystack = (track['title'] + ' ' + track.get('artist', '')).casefold()
            button.set_visible(not query or query in haystack)

    def update_current(self, uri):
        self.current_uri = uri
        for button, track in self.track_buttons:
            context = button.get_style_context()
            if track['uri'] == uri:
                context.add_class('current-track')
            else:
                context.remove_class('current-track')

    def on_refresh(self, _button):
        if self.selected:
            self.select_collection(None, self.selected)
        else:
            self.load_home()

    def on_connect(self, _button):
        self.connect_spotify()
        self.notice.set_text('Открываю Spotify…')
        GLib.timeout_add_seconds(4, self._retry)

    def _retry(self):
        self.on_refresh(None)
        return False
