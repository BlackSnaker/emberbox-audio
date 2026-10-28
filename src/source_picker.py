"""Small tactile source selector, also reachable on the compact cover."""
import os
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Pango

RU = os.environ.get('EMBERBOX_LANGUAGE', os.environ.get('LANG', 'en')).startswith('ru')


def text(en, ru):
    return ru if RU else en


class SourcePicker:
    def __init__(self, changed, launch, accounts=None):
        self.changed, self.launch = changed, launch
        self.accounts = accounts
        self.popover = None

    def show(self, anchor, source, sessions, binding, youtube_binding='', youtube_mode='native'):
        if self.popover:
            self.popover.destroy()
        popup = self.popover = Gtk.Popover.new(anchor)
        popup.get_style_context().add_class('source-popover')
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        box.set_border_width(12)
        box.set_size_request(260, -1)
        popup.add(box)

        def button(label, callback):
            item = Gtk.Button(label=label)
            item.get_style_context().add_class('filter-chip')
            item.set_halign(Gtk.Align.FILL)
            item.connect('clicked', lambda _b: (popup.popdown(), callback()))
            box.pack_start(item, False, False, 0)
            return item

        for key, name in [('spotify', 'Spotify'), ('apple-music', 'Apple Music · '+text('Your library','медиатека')), ('youtube', 'YouTube · '+text('Search & play', 'поиск и музыка')), ('yandex-music',text('Yandex Music · My Wave','Яндекс Музыка · Моя волна'))]:
            button(('●  ' if source == key else '○  ') + name,
                   lambda k=key: self.changed(k, None))
        for session in sessions:
            if session.name.startswith('org.mpris.MediaPlayer2.spotify'):
                button(text('Spotify · desktop client (optional)','Spotify · настольный клиент (необязательно)'),lambda s=session:self.changed('spotify',s))
        browsers = [session for session in sessions if session.family]
        if browsers:
            label = Gtk.Label(label=text('Browser sessions · Apple Music / YouTube', 'Сеансы браузера · Apple Music / YouTube'))
            label.get_style_context().add_class('caption')
            box.pack_start(label, False, False, 3)
        for session in browsers:
            title = str(session.metadata.get('xesam:title', ''))[:34]
            site = 'youtube' if session.youtube else 'apple-music' if session.apple else 'youtube' if source == 'youtube' else 'apple-music'
            selected_binding = youtube_binding if site == 'youtube' else binding
            prefix = 'YouTube' if site == 'youtube' else 'Apple Music'
            name = ('✓  ' if selected_binding == session.binding else '') + prefix + ' · ' + session.identity
            if title:
                name += '\n' + title
            button(name, lambda s=session, service=site: self.changed(service, s))
        hint = Gtk.Label(label=text(
            'Spotify, Apple Music, Yandex Music and YouTube play inside Emberbox. You can also select a browser session.\n'
            'Browser controls and sound may be shared with other tabs.',
            'Spotify, Apple Music, Яндекс Музыка и YouTube играют прямо в плеере. Можно также выбрать сеанс браузера.\n'
            'Управление и звук браузера могут быть общими для вкладок.') if browsers else text(
                'Spotify, Apple Music, Yandex Music and YouTube play inside Emberbox.',
                'Spotify, Apple Music, Яндекс Музыка и YouTube играют прямо в плеере.'))
        hint.set_line_wrap(True)
        hint.set_max_width_chars(34)
        hint.get_style_context().add_class('caption')
        box.pack_start(hint, False, False, 3)
        if self.accounts:
            button(text('Connect accounts…','Подключить аккаунты…'),self.accounts)
        popup.show_all()
        popup.popup()
