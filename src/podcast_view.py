"""A bounded desktop podcast library with independent provider selection."""
from concurrent.futures import ThreadPoolExecutor

from gi.repository import GLib, Gtk, Pango

from podcast_catalog import APPLE, PROVIDERS, PodcastCatalog
from podcast_discovery import CATEGORIES, LANGUAGES, PodcastDiscovery, preferences, save_preferences, showcase
from service_icons import service_icon
from source_picker import text


CSS = b'''
.podcast-hero {
  border-radius: 24px; padding: 14px 19px;
  background-image: linear-gradient(119deg, rgba(226,194,161,.15), rgba(117,135,144,.065) 35%, rgba(27,31,34,.27) 63%, rgba(181,122,73,.13));
  border: 1px solid rgba(237,215,191,.20);
  box-shadow: inset 0 1px rgba(255,246,232,.19), inset 0 -1px rgba(155,186,201,.10), 0 6px 20px rgba(5,8,10,.19);
}
.podcast-heading { color: #f9e8cf; font-size: 30px; font-weight: bold; }
.podcast-muted { color: #d0bfa5; font-size: 12px; }
.ember-stage button.podcast-provider:checked, .ember-stage button.podcast-category:checked {
  background-image: linear-gradient(119deg, rgba(255,213,163,.19), rgba(218,151,100,.10) 45%, rgba(160,196,212,.14));
  color: #fff0d2;
  border-color: rgba(251,221,183,.36);
  box-shadow: inset 0 1px rgba(255,247,231,.28), inset 0 -1px rgba(167,204,223,.13);
}
.ember-stage button.podcast-category { padding: 5px 10px; }
.ember-stage .podcast-language button {
  color: #f0ddc6; background-image: linear-gradient(to bottom right, rgba(234,213,191,.16), rgba(141,170,192,.07));
  border: 1px solid rgba(234,208,182,.24); border-radius: 17px; box-shadow: inset 0 1px rgba(255,245,225,.13);
}
.podcast-wall flowboxchild { padding: 0; background: transparent; }
.ember-stage button.podcast-tile {
  color: #f4e5ce; padding: 10px; border-radius: 18px;
  background-image: linear-gradient(138deg, rgba(241,211,179,.145), rgba(91,108,124,.09) 45%, rgba(19,23,28,.31) 73%, rgba(143,107,81,.10));
  border: 1px solid rgba(236,212,188,.18);
  box-shadow: inset 0 1px rgba(255,244,228,.16), inset 0 -1px rgba(157,194,215,.12), 0 4px 15px rgba(0,0,0,.17);
}
.ember-stage button.podcast-tile:hover, .ember-stage button.podcast-tile:focus {
  background-image: linear-gradient(138deg, rgba(254,212,165,.22), rgba(145,171,196,.16) 53%, rgba(33,38,45,.26));
  border-color: rgba(253,218,180,.43);
}
.podcast-tile .podcast-title { color: #f4e5ce; font-weight: bold; }
.podcast-tile .podcast-card-meta { color: #d6c4ad; font-size: 10px; }
.ember-stage button.podcast-result {
  padding: 10px 14px; border-radius: 17px;
  background-image: linear-gradient(115deg, rgba(234,212,185,.10), rgba(21,24,29,.63) 55%, rgba(104,125,144,.10));
  border: 1px solid rgba(235,207,173,.15);
  box-shadow: inset 0 1px rgba(255,231,200,.11);
}
.ember-stage button.podcast-result:hover, .ember-stage button.podcast-result:focus {
  border-color: rgba(255,214,155,.38);
  background-color: rgba(192,136,71,.14);
}
.podcast-result .podcast-title { color: #f1e3ca; font-size: 15px; font-weight: 700; }
.podcast-result .podcast-number, .podcast-result .podcast-duration {
  color: #d4bea2; font-size: 12px; font-feature-settings: "tnum";
}
.podcast-result .podcast-play {
  color: #f5d6a5; border-radius: 21px;
  background-image: linear-gradient(140deg, rgba(255,221,169,.21), rgba(111,133,151,.07));
  border: 1px solid rgba(255,222,173,.20);
  box-shadow: inset 0 1px rgba(255,239,217,.13);
}
'''


def caption(value, style):
    label = Gtk.Label(label=value, xalign=0)
    label.get_style_context().add_class(style)
    label.set_ellipsize(Pango.EllipsizeMode.END)
    return label


class PodcastView(Gtk.Box):
    def __init__(self, host, artwork, accounts):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.host, self.artwork, self.accounts = host, artwork, accounts
        self.catalogue = PodcastCatalog(host)
        self.discovery = PodcastDiscovery(self.catalogue)
        self.pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix='ember-podcasts')
        self.future = None
        self.generation = 0
        self.closed = False
        self.provider = APPLE
        self.language, self.category = preferences()
        self.started = False
        self.selecting = False
        self.open_show = None
        self.results = []
        self.terms = {}

        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        hero.get_style_context().add_class('podcast-hero')
        heading = Gtk.Box(spacing=10)
        self.show_art = Gtk.Image()
        self.show_art.set_no_show_all(True)
        heading.pack_start(self.show_art, False, False, 0)
        self.heading = caption(text('Podcasts', 'Подкасты'), 'podcast-heading')
        heading.pack_start(self.heading, True, True, 0)
        self.sign_in = self.button(text('Accounts', 'Аккаунты'), lambda: self.accounts())
        self.sign_in.set_no_show_all(True)
        heading.pack_end(self.sign_in, False, False, 0)
        self.language_menu = Gtk.ComboBoxText()
        self.language_menu.get_style_context().add_class('podcast-language')
        self.language_menu.get_accessible().set_name(text('Podcast language', 'Язык подкастов'))
        for key, (name, _market) in LANGUAGES.items():
            self.language_menu.append(key, name)
        self.language_menu.set_active_id(self.language)
        self.language_menu.connect('changed', self.change_language)
        heading.pack_end(self.language_menu, False, False, 0)
        hero.pack_start(heading, False, False, 0)
        providers = Gtk.Box(spacing=5)
        self.providers = {}
        for key, name in PROVIDERS.items():
            row = Gtk.Box(spacing=6)
            row.pack_start(service_icon('apple-music' if key == APPLE else key, 23), False, False, 0)
            row.pack_start(Gtk.Label(label=name), False, False, 0)
            button = self.providers[key] = Gtk.ToggleButton()
            button.get_style_context().add_class('stage-quiet')
            button.get_style_context().add_class('podcast-provider')
            button.get_accessible().set_name(name)
            button.add(row)
            button.connect('clicked', lambda _button, provider=key: self.select(provider))
            providers.pack_start(button, False, False, 0)
        hero.pack_start(providers, False, False, 0)
        search = Gtk.Box(spacing=8)
        self.back = self.button(text('‹ Shows', '‹ Подкасты'), self.back_to_shows)
        self.back.set_no_show_all(True)
        search.pack_start(self.back, False, False, 0)
        self.entry = Gtk.SearchEntry(max_length=200)
        self.entry.get_style_context().add_class('stage-search')
        self.entry.connect('activate', lambda _entry: self.search())
        self.entry.connect('stop-search', lambda _entry: self.search())
        search.pack_start(self.entry, True, True, 0)
        search.pack_end(self.button(text('Search', 'Найти'), self.search), False, False, 0)
        hero.pack_start(search, False, False, 0)
        categories = Gtk.Box(spacing=5)
        self.categories = {}
        for key, (name, _genre) in CATEGORIES.items():
            button = self.categories[key] = Gtk.ToggleButton(label=name)
            button.get_style_context().add_class('stage-quiet')
            button.get_style_context().add_class('podcast-category')
            button.connect('clicked', lambda _button, value=key: self.change_category(value))
            categories.pack_start(button, False, False, 0)
        self.categories[self.category].set_active(True)
        hero.pack_start(categories, False, False, 0)
        self.pack_start(hero, False, False, 0)

        status = Gtk.Box(spacing=7)
        self.spinner = Gtk.Spinner()
        self.spinner.set_no_show_all(True)
        status.pack_start(self.spinner, False, False, 0)
        self.note = caption('', 'podcast-muted')
        status.pack_start(self.note, True, True, 0)
        self.pack_start(status, False, False, 0)
        scroll = self.scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.get_style_context().add_class('stage-library-scroll')
        self.content = Gtk.Stack(hhomogeneous=False, vhomogeneous=False)
        self.wall = Gtk.FlowBox(homogeneous=True, min_children_per_line=2, max_children_per_line=8,
                               row_spacing=10, column_spacing=10, selection_mode=Gtk.SelectionMode.NONE,
                               valign=Gtk.Align.START)
        self.wall.get_style_context().add_class('podcast-wall')
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_end=8, margin_bottom=10)
        self.content.add_named(self.wall, 'wall')
        self.content.add_named(self.list, 'episodes')
        scroll.add(self.content)
        self.pack_start(scroll, True, True, 0)
        self.select(APPLE, refresh=False)

    def activate(self):
        if not self.started:
            self.search()

    def change_language(self, menu):
        language = menu.get_active_id()
        if language in LANGUAGES and language != self.language:
            self.language = language
            self.filter_changed()

    def change_category(self, category):
        if self.selecting or not hasattr(self, 'content'):
            return
        self.selecting = True
        try:
            for key, button in self.categories.items():
                if button.get_active() != (key == category):
                    button.set_active(key == category)
        finally:
            self.selecting = False
        if category != self.category:
            self.category = category
            self.filter_changed()

    def filter_changed(self):
        save_preferences(self.language, self.category)
        self.search()

    def button(self, label, callback):
        button = Gtk.Button(label=label)
        button.get_style_context().add_class('stage-quiet')
        button.connect('clicked', lambda _button: callback())
        return button

    def select(self, provider, refresh=True):
        if self.selecting:
            return
        self.selecting = True
        try:
            for key, button in self.providers.items():
                if button.get_active() != (key == provider):
                    button.set_active(key == provider)
        finally:
            self.selecting = False
        if self.provider != provider:
            self.terms[self.provider] = self.entry.get_text()
            self.provider = provider
            self.entry.set_text(self.terms.get(provider, ''))
        self.sign_in.set_visible(provider != APPLE)
        self.entry.set_placeholder_text(text('Show name', 'Название подкаста') if provider == APPLE else
                                        text('Podcast or episode name', 'Название подкаста или выпуска'))
        if refresh:
            self.search()

    def back_to_shows(self):
        self.search()

    def set_busy(self, running):
        self.spinner.set_visible(running)
        if running:
            self.spinner.start()
        else:
            self.spinner.stop()

    def search(self):
        self.request(self.entry.get_text().strip())

    def request(self, term, show=None):
        self.started = True
        self.cancel()
        self.open_show = show
        self.show_art.set_visible(bool(show))
        if show:
            self.artwork.load(self.show_art, show.get('image', ''), 56, 9)
        self.back.set_visible(bool(show))
        self.heading.set_text(show['title'] if show else text('Podcasts', 'Подкасты'))
        browsing = not term and not show
        self.content.set_visible_child_name('episodes' if show else 'wall')
        self.scroll.get_vadjustment().set_value(0)
        initial = showcase(self.provider, self.language, self.category) if browsing else []
        if browsing and self.provider != APPLE and len(initial) < 8:
            # Keep the selected language even when the native shelf is small.
            existing = {item['title'].casefold() for item in initial}
            public = [dict(item, provider=APPLE) for item in showcase(APPLE, self.language, self.category)
                      if item['title'].casefold() not in existing]
            initial += public[:max(0, 12-len(initial))]
        self.render(initial)
        if browsing and (self.provider != APPLE or self.language == 'all'):
            self.set_caption(initial, browsing=True)
            return
        provider, current = self.provider, self.generation
        self.set_busy(not browsing or not initial)
        if show:
            self.note.set_text(text('Loading episodes…', 'Загружаю выпуски…'))
            request = (self.catalogue.load, provider, term, show)
        elif browsing:
            self.set_caption(initial, browsing=True)
            request = (self.discovery.browse, provider, self.language, self.category)
        else:
            self.note.set_text(text('Searching…', 'Ищу…'))
            request = (self.discovery.search, provider, term, self.language, self.category)
        self.future = self.pool.submit(*request)
        self.future.add_done_callback(lambda result: GLib.idle_add(
            self.loaded, current, result, browsing, priority=GLib.PRIORITY_DEFAULT))

    def loaded(self, generation, future, browsing):
        if self.closed or generation != self.generation:
            return False
        self.set_busy(False)
        try:
            values = future.result()
        except Exception as error:
            if browsing and self.results:
                return False
            if self.provider == APPLE:
                message = text('Could not load this Apple Podcasts catalogue or feed.',
                               'Не удалось загрузить каталог Apple Podcasts или ленту издателя.')
            else:
                message = str(error)
            self.note.set_text(message)
            return False
        old_ids = [item['id'] for item in self.results]
        new_ids = [item['id'] for item in values]
        if browsing and old_ids and new_ids[:len(old_ids)] == old_ids:
            for item in values[len(old_ids):]:
                self.add_tile(item)
            self.results = values
            self.wall.show_all()
        elif old_ids != new_ids:
            self.render(values)
        self.set_caption(values, browsing)
        return False

    def set_caption(self, values, browsing):
        if not values:
            self.note.set_text(text('No podcasts match these filters. Try another category or language.',
                                    'Нет подкастов с такими фильтрами. Попробуй другую категорию или язык.'))
            return
        providers = list(dict.fromkeys(PROVIDERS[item.get('provider', self.provider)] for item in values))
        provider = ' · '.join(providers)
        if browsing and not self.open_show:
            name = CATEGORIES[self.category][0] if self.category != 'all' else text('Featured', 'Подборка')
            self.note.set_text(f'{name}  ·  {LANGUAGES[self.language][0]}  ·  {provider}')
        elif self.open_show:
            self.note.set_text(text('Episodes', 'Выпуски') + '  ·  ' + provider)
        else:
            self.note.set_text(provider)

    def render(self, values):
        for container in (self.wall, self.list):
            for child in container.get_children():
                child.destroy()
        self.results = values
        self.rendered = 0
        if self.open_show:
            self.render_more()
        else:
            for item in values:
                self.add_tile(item)
            self.wall.show_all()

    def add_tile(self, item):
        tile = Gtk.Button()
        tile.get_style_context().add_class('podcast-tile')
        tile.get_accessible().set_name(item['title'])
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        art = Gtk.Image(halign=Gtk.Align.CENTER)
        self.artwork.load(art, item.get('image', ''), 142, 11)
        body.pack_start(art, False, False, 0)
        title = Gtk.Label(label=item['title'], xalign=0, lines=2, max_width_chars=16)
        title.set_line_wrap(True)
        title.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.get_style_context().add_class('podcast-title')
        title.set_size_request(-1, title.create_pango_layout('Ag\nAg').get_pixel_size()[1])
        body.pack_start(title, False, False, 0)
        info = [CATEGORIES[key][0] for key in item.get('categories', [])[:1] if key in CATEGORIES]
        if item.get('language') in LANGUAGES:
            info.append(LANGUAGES[item['language']][0])
        if item.get('provider'):
            info.append(PROVIDERS[item['provider']])
        if not info:
            info.append(item.get('artist') or (text('Episode', 'Выпуск') if item['kind']=='episode' else PROVIDERS[self.provider]))
        body.pack_start(caption(' · '.join(info), 'podcast-card-meta'), False, False, 0)
        tile.add(body)
        tile.connect('clicked', lambda _button: self.activate_item(item))
        self.wall.add(tile)

    def render_more(self):
        end = min(self.rendered + 30, len(self.results))
        for index in range(self.rendered, end):
            item = self.results[index]
            show = item['kind'] == 'show'
            button = Gtk.Button()
            button.get_style_context().add_class('podcast-result')
            button.get_accessible().set_name(item['title'])
            row = Gtk.Box(spacing=16)
            if self.open_show:
                picture = caption(f'{index + 1:02d}', 'podcast-number')
                picture.set_size_request(36, -1)
                picture.set_xalign(.5)
            else:
                picture = Gtk.Image()
                self.artwork.load(picture, item.get('image', ''), 44, 7)
            row.pack_start(picture, False, False, 0)
            description = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, valign=Gtk.Align.CENTER)
            title = caption(item['title'], 'podcast-title')
            title.set_line_wrap(True)
            title.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            title.set_lines(2)
            description.pack_start(title, False, False, 0)
            row.pack_start(description, True, True, 0)
            seconds = item.get('duration_ms', 0) // 1000
            action = caption('›' if show else '▶', 'podcast-play')
            action.set_size_request(40, 40)
            action.set_xalign(.5)
            action.set_valign(Gtk.Align.CENTER)
            row.pack_end(action, False, False, 0)
            duration = caption(f'{seconds // 60}:{seconds % 60:02d}' if seconds else '', 'podcast-duration')
            duration.set_size_request(48, -1)
            duration.set_xalign(1)
            row.pack_end(duration, False, False, 0)
            button.add(row)
            button.connect('clicked', lambda _button, selected=item: self.activate_item(selected))
            self.list.pack_start(button, False, False, 0)
        self.rendered = end
        if end < len(self.results):
            def more():
                control.destroy()
                self.render_more()
            label = text('Show more episodes', 'Показать ещё выпуски') if self.open_show else text('Show more', 'Показать ещё')
            control = self.button(label, more)
            control.set_halign(Gtk.Align.CENTER)
            self.list.pack_start(control, False, False, 0)
        self.list.show_all()

    def activate_item(self, item):
        source = item.get('provider', self.provider)
        if source != self.provider:
            self.select(source, refresh=False)
        if item['kind'] == 'show':
            self.request(self.entry.get_text().strip(), item)
            return
        episodes = [value for value in self.results if value['kind'] == 'episode']
        self.host.play_podcast(self.provider, item, episodes)

    def cancel(self):
        self.generation += 1
        if self.future:
            self.future.cancel()
            self.future = None
        self.set_busy(False)

    def close(self):
        self.closed = True
        self.cancel()
        self.pool.shutdown(wait=False, cancel_futures=True)
