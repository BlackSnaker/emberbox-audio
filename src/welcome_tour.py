"""Three short, bilingual guide screens with optional account setup."""
from gi.repository import Gdk, Gtk, Pango

from ember_brand import BrandIgnition
from paths import CONFIG_DIR
from service_icons import service_icon
from source_picker import text


SEEN = CONFIG_DIR / 'welcome-tour-seen'
CSS = b'''
.ember-welcome, .ember-welcome .titlebar {
  color: #f5e8d4; background-color: #181a1b;
  background-image: linear-gradient(to bottom right, #302720, #191b1d 72%);
}
.ember-welcome decoration {
  border: 1px solid #59473a; border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0,0,0,.42);
}
.ember-welcome.solid-csd decoration {
  background-color: #3f3329; margin: 0; padding: 0; box-shadow: none;
}
.ember-welcome .titlebar { border-bottom: 1px solid rgba(230,181,118,.16); }
.ember-welcome .welcome-hero {
  background-image: linear-gradient(to bottom right, #231f1c, #32251d 70%, #4c3325);
  border-radius: 22px; border: 1px solid rgba(255,202,137,.21);
  box-shadow: inset 0 1px rgba(255,230,189,.12);
  padding: 24px;
}
.ember-welcome .welcome-title { color: #fff0d5; font-size: 30px; font-weight: 700; }
.ember-welcome .welcome-copy { color: #dfcdb6; font-size: 13px; }
.ember-welcome .welcome-label { color: #edc397; font-size: 11px; font-weight: 700; }
.ember-welcome .welcome-well {
  background-image: linear-gradient(to bottom right, rgba(239,196,153,.10), rgba(239,196,153,.035));
  border: 1px solid rgba(233,191,157,.16); border-radius: 12px; padding: 8px 10px;
}
.ember-welcome button {
  color: #f3dfc3; background-image: none; background-color: #322d28;
  border: 1px solid #604d3b; border-radius: 11px; padding: 7px 12px;
}
.ember-welcome button:hover { background-color: #49382a; }
.ember-welcome button:focus { outline: 1px solid #fbc68e; outline-offset: -3px; }
.ember-welcome button.welcome-primary {
  color: #281b13; font-weight: 700;
  background-image: linear-gradient(to bottom, #ffd499, #e9a669);
  border-color: #ffdaa5;
}
.ember-welcome button.welcome-primary:hover {
  background-image: linear-gradient(to bottom, #ffe3b9, #efaf70);
}
.ember-welcome .welcome-step { background-color: #514236; border-radius: 3px; }
.ember-welcome .welcome-step.active { background-color: #ffc480; }
'''


def label(value, style):
    item = Gtk.Label(label=value, xalign=0)
    item.set_line_wrap(True)
    item.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    item.set_max_width_chars(44)
    item.get_style_context().add_class(style)
    return item


class WelcomeTour(Gtk.Window):
    def __init__(self, parent, accounts, seen=SEEN):
        title = text('Meet Ember', 'Знакомство с Ember')
        super().__init__(title=title, transient_for=parent, modal=True, destroy_with_parent=True)
        self.seen = seen
        self.accounts = accounts
        self.index = 0
        self.get_style_context().add_class('ember-welcome')
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_skip_taskbar_hint(True)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        monitor = parent.get_display().get_monitor_at_window(parent.get_window())
        width, height = 590, 398
        if monitor:
            area = monitor.get_workarea()
            width, height = min(width, area.width - 32), min(height, area.height - 72)
        self.set_default_size(width, height)
        self.connect('delete-event', lambda *_: self.finish())
        self.connect('key-press-event', self.on_key)

        header = Gtk.HeaderBar(title=title, show_close_button=True)
        self.set_titlebar(header)
        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16, border_width=18)
        self.add(layout)
        self.pages = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=220)
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                    vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.pages)
        layout.pack_start(scroll, True, True, 0)
        self.pages.add_named(self.intro(), '0')
        self.pages.add_named(self.sources(), '1')
        self.pages.add_named(self.listening(), '2')

        footer = Gtk.Box(spacing=8)
        footer_overlay = Gtk.Overlay()
        footer_overlay.add(footer)
        self.skip = self.button(text('Skip', 'Пропустить'), self.finish)
        self.back = self.button(text('Back', 'Назад'), lambda: self.show_page(self.index - 1))
        self.next = self.button('', self.advance, primary=True)
        for button in (self.skip, self.back):
            button.set_no_show_all(True)
            footer.pack_start(button, False, False, 0)
        footer.pack_end(self.next, False, False, 0)
        progress = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.steps = [Gtk.Box(width_request=16, height_request=4) for _ in range(3)]
        for dot in self.steps:
            dot.get_style_context().add_class('welcome-step')
            progress.pack_start(dot, False, False, 0)
        self.progress = progress
        footer_overlay.add_overlay(progress)
        footer_overlay.set_overlay_pass_through(progress, True)
        layout.pack_end(footer_overlay, False, False, 0)

    def button(self, title, callback, primary=False):
        button = Gtk.Button(label=title)
        if primary:
            button.get_style_context().add_class('welcome-primary')
        button.connect('clicked', lambda *_: callback())
        return button

    def page(self, title, copy):
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=11)
        column.get_style_context().add_class('welcome-hero')
        column.pack_start(label(title, 'welcome-title'), False, False, 0)
        column.pack_start(label(copy, 'welcome-copy'), False, False, 0)
        return column

    def intro(self):
        column = self.page(text('Your music. A little warmer.', 'Твоя музыка. Чуть теплее.'),
                           text('Keep Ember close as a desktop widget, or open it fullscreen to settle into an album.',
                                'Оставь Ember под рукой на рабочем столе или разверни на весь экран, чтобы погрузиться в альбом.'))
        self.mark = BrandIgnition(persistent=True)
        self.mark.set_size_request(126, 136)
        column.pack_start(self.mark, True, True, 0)
        column.reorder_child(self.mark, 0)
        return column

    def sources(self):
        column = self.page(text('Bring your music', 'Выбери свой источник'),
                           text('Choose your service in the player header. Connect your account to bring in your library.',
                                'Выбери сервис в шапке плеера. Подключи аккаунт, чтобы открыть свою медиатеку.'))
        grid = Gtk.Grid(column_spacing=8, row_spacing=8, column_homogeneous=True)
        for index, (key, name) in enumerate((
            ('apple-music', 'Apple Music'), ('spotify', 'Spotify'),
            ('youtube', 'YouTube'), ('yandex-music', text('Yandex Music', 'Яндекс Музыка')),
        )):
            badge = Gtk.Box(spacing=8)
            badge.get_style_context().add_class('welcome-well')
            badge.pack_start(service_icon(key, 28), False, False, 0)
            badge.pack_start(label(name, 'welcome-label'), True, True, 0)
            grid.attach(badge, index % 2, index // 2, 1, 1)
        column.pack_start(grid, False, False, 0)
        connect = self.button(text('Open accounts', 'Открыть аккаунты'), lambda: self.finish(connect=True))
        connect.set_halign(Gtk.Align.START)
        column.pack_start(connect, False, False, 0)
        return column

    def listening(self):
        column = self.page(text('Make it yours', 'Настрой Ember под себя'),
                           text('Press F11 or use the fullscreen button for the full player.',
                                'Нажми F11 или кнопку разворота, чтобы открыть полноэкранный плеер.'))
        for name, copy in (
            (text('Themes', 'Темы'), text('Pick a look in Settings → Look.', 'Выбери оформление в «Настройки → Вид».')),
            ('EmberFlow', text('Blend tracks in your queue.', 'Смешивай треки из очереди при переходе.')),
            ('Ember DJ', text('Ask for music by mood, genre or artist.', 'Попроси музыку под настроение, назови жанр или артиста.')),
        ):
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            row.get_style_context().add_class('welcome-well')
            row.pack_start(label(name, 'welcome-label'), False, False, 0)
            row.pack_start(label(copy, 'welcome-copy'), False, False, 0)
            column.pack_start(row, False, False, 0)
        return column

    def open(self):
        self.show_all()
        self.show_page(0)
        self.next.grab_focus()
        self.present()
        self.mark.ignite(132)

    def show_page(self, index):
        self.index = index
        self.pages.set_visible_child_name(str(index))
        self.skip.set_visible(index == 0)
        self.back.set_visible(index > 0)
        self.next.set_label(text('Open player', 'К плееру') if index == 2 else text('Continue', 'Далее'))
        self.progress.get_accessible().set_name(text('Step {} of 3', 'Шаг {} из 3').format(index + 1))
        for i, dot in enumerate(self.steps):
            style = dot.get_style_context()
            (style.add_class if i == index else style.remove_class)('active')

    def advance(self):
        if self.index == 2:
            self.finish()
        else:
            self.show_page(self.index + 1)

    def on_key(self, _window, event):
        if event.keyval == Gdk.KEY_Escape:
            return self.finish()
        return False

    def finish(self, connect=False):
        try:
            self.seen.parent.mkdir(parents=True, exist_ok=True)
            self.seen.touch(exist_ok=True)
        except OSError as error:
            print(f'Could not save Ember welcome preference: {error}', flush=True)
        self.destroy()
        if connect:
            self.accounts()
        return True
