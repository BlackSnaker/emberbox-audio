"""Small tactile source selector, also reachable on the compact cover."""
import os
from gi.repository import Gtk, Pango

RU = os.environ.get('EMBERBOX_LANGUAGE', os.environ.get('LANG', 'en')).startswith('ru')


def text(en, ru):
    return ru if RU else en


class SourcePicker:
    def __init__(self, changed, launch):
        self.changed, self.launch = changed, launch
        self.popover = None

    def show(self, anchor, source, sessions, binding):
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

        for key, name in [('spotify', 'Spotify'), ('apple-music', 'Apple Music')]:
            button(('●  ' if source == key else '○  ') + name,
                   lambda k=key: self.changed(k, None))
        label = Gtk.Label(label=text('Apple Music · browser session', 'Apple Music · сеанс браузера'))
        label.get_style_context().add_class('caption')
        box.pack_start(label, False, False, 3)
        browsers = [session for session in sessions if session.family]
        for session in browsers:
            title = str(session.metadata.get('xesam:title', ''))[:34]
            name = ('✓  ' if binding == session.binding else '') + session.identity
            if title:
                name += '\n' + title
            button(name, lambda s=session: self.changed('apple-music', s))
        hint = Gtk.Label(label=text(
            'Start a song at music.apple.com, then select its browser here.\n'
            'Browser controls and sound may be shared with other tabs.',
            'Включи трек на music.apple.com и выбери его браузер здесь.\n'
            'Управление и звук браузера могут быть общими для вкладок.'))
        hint.set_line_wrap(True)
        hint.set_max_width_chars(34)
        hint.get_style_context().add_class('caption')
        box.pack_start(hint, False, False, 3)
        button(text('Open Apple Music ↗', 'Открыть Apple Music ↗'), self.launch)
        popup.show_all()
        popup.popup()
