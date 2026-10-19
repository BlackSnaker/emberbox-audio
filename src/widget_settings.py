"""A small Grunesphism settings popover; no hover labels or focus frames."""
from gi.repository import Gtk
from source_picker import text


def settings_button(callback):
    button = Gtk.Button()
    icon = Gtk.Image.new_from_icon_name('emblem-system-symbolic', Gtk.IconSize.MENU)
    icon.set_pixel_size(14)
    button.add(icon)
    button.get_style_context().add_class('mini-button')
    button.get_style_context().add_class('settings-button')
    button.get_accessible().set_name(text('Player settings', 'Настройки плеера'))
    button.connect('clicked', callback)
    return button


class SettingsMenu:
    def __init__(self, compact, refresh, restart, accounts=None):
        self.compact, self.refresh, self.restart = compact, refresh, restart
        self.accounts = accounts
        self.popover = None

    def show(self, anchor, compact, source):
        if self.popover:
            self.popover.destroy()
        popup = self.popover = Gtk.Popover.new(anchor)
        popup.get_style_context().add_class('settings-popover')
        popup.set_position(Gtk.PositionType.BOTTOM)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        box.set_border_width(12)
        box.set_size_request(228, -1)
        popup.add(box)
        heading = Gtk.Label(label=text('Player settings', 'Настройки плеера'))
        heading.set_xalign(0)
        heading.get_style_context().add_class('drawer-heading')
        box.pack_start(heading, False, False, 0)
        caption = Gtk.Label(label=source)
        caption.set_xalign(0)
        caption.get_style_context().add_class('caption')
        box.pack_start(caption, False, False, 2)

        def action(label, callback, style='filter-chip'):
            button = Gtk.Button(label=label)
            button.get_style_context().add_class(style)
            button.get_style_context().add_class('settings-action')
            button.connect('clicked', lambda _button: (popup.popdown(), callback()))
            box.pack_start(button, False, False, 0)
            return button

        if self.accounts:
            self.accounts_button = action(text('Accounts · Spotify / Apple / Yandex','Аккаунты · Spotify / Apple / Яндекс'),self.accounts)
        self.mode_button = action(
            text('Full player', 'Обычный режим') if compact else text('Compact player', 'Компактный режим'),
            self.compact)
        self.refresh_button = action(text('Refresh connections', 'Обновить подключения'), self.refresh)
        self.restart_button = action(text('Restart widget', 'Перезапустить виджет'), self.restart, 'warm-button')
        popup.show_all()
        popup.popup()
