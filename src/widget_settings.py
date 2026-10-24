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


def window_button(icon_name, label, callback):
    button=Gtk.Button()
    icon=Gtk.Image.new_from_icon_name(icon_name,Gtk.IconSize.MENU)
    icon.set_pixel_size(14);button.add(icon)
    button.get_style_context().add_class('mini-button')
    button.get_style_context().add_class('settings-button')
    button.get_accessible().set_name(label)
    button.connect('clicked',lambda _button:callback())
    return button


class SettingsMenu:
    def __init__(self, compact, refresh, restart, accounts=None, fullscreen=None, hide=None, quit=None, dj=None):
        self.compact, self.refresh, self.restart = compact, refresh, restart
        self.accounts,self.fullscreen = accounts,fullscreen
        owner=getattr(fullscreen,'__self__',None)
        self.dj=dj or ((lambda:self.open_dj(owner)) if owner else None)
        self.hide,self.quit = hide,quit
        self.popover = None

    def open_dj(self,host):
        from fullscreen import FullscreenPlayer
        if host.fullscreen is None:host.fullscreen=FullscreenPlayer(host)
        host.fullscreen.open_dj()

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
        if getattr(self,'flow',None):
            from flow_control import FlowControl
            box.pack_start(FlowControl(self.flow),False,False,3)
            note=Gtk.Label(label=self.flow.message);note.set_line_wrap(True);note.set_max_width_chars(30)
            note.set_xalign(0);note.get_style_context().add_class('caption');box.pack_start(note,False,False,2)

        def action(label, callback, style='filter-chip'):
            button = Gtk.Button(label=label)
            button.get_style_context().add_class(style)
            button.get_style_context().add_class('settings-action')
            button.connect('clicked', lambda _button: (popup.popdown(), callback()))
            box.pack_start(button, False, False, 0)
            return button

        if self.fullscreen:
            self.fullscreen_button = action(text('Listening room · Fullscreen','Комната прослушивания · На весь экран'),self.fullscreen)
        if self.dj:self.dj_button=action(text('Ember DJ · Your own radio','Ember DJ · Личное радио'),self.dj)
        if self.accounts:
            self.accounts_button = action(text('Accounts · Spotify / Apple / Yandex','Аккаунты · Spotify / Apple / Яндекс'),self.accounts)
        self.mode_button = action(
            text('Full player', 'Обычный режим') if compact else text('Compact player', 'Компактный режим'),
            self.compact)
        self.refresh_button = action(text('Refresh connections', 'Обновить подключения'), self.refresh)
        self.restart_button = action(text('Restart widget', 'Перезапустить виджет'), self.restart, 'warm-button')
        if self.hide:self.hide_button=action(text('Hide player','Скрыть плеер'),self.hide)
        if self.quit:self.quit_button=action(text('Close player','Закрыть плеер'),self.quit)
        popup.show_all()
        popup.popup()
