"""Sectioned desktop settings on a small, tactile liquid-glass surface."""
from gi.repository import Gtk
from source_picker import text
from glass_menu import GlassPopover, label


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


def window_button(icon_name, name, callback):
    button = Gtk.Button()
    icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
    icon.set_pixel_size(14)
    button.add(icon)
    button.get_style_context().add_class('mini-button')
    button.get_style_context().add_class('settings-button')
    button.get_accessible().set_name(name)
    button.connect('clicked', lambda _button: callback())
    return button


class SettingsMenu:
    def __init__(self, compact, refresh, restart, accounts=None, fullscreen=None, hide=None, quit=None, dj=None):
        self.compact, self.refresh, self.restart = compact, refresh, restart
        self.accounts, self.fullscreen = accounts, fullscreen
        owner = getattr(fullscreen, '__self__', None)
        self.dj = dj or ((lambda: self.open_dj(owner)) if owner else None)
        self.hide, self.quit = hide, quit
        self.popover = None
        self.section = 'player'
        self.selecting = False

    def open_dj(self, host):
        from fullscreen import FullscreenPlayer
        if host.fullscreen is None:
            host.fullscreen = FullscreenPlayer(host)
        host.fullscreen.open_dj()

    def popups_for(self, window):
        for popup in (self.popover, getattr(self, 'scene_popup', None)):
            anchor = popup.get_relative_to() if popup else None
            if anchor and anchor.get_toplevel() is window:
                yield popup

    def dismiss_for(self, window):
        for popup in tuple(self.popups_for(window)):
            popup.dismiss()

    def is_open_for(self, window):
        return any(popup.get_mapped() for popup in self.popups_for(window))

    def select_section(self, name):
        if self.selecting or name not in self.section_buttons:
            return
        self.selecting = True
        self.section = name
        try:
            for key, button in self.section_buttons.items():
                button.set_active(key == name)
            self.stack.set_visible_child_name(name)
            self.navigation.select(self.section_buttons[name])
        finally:
            self.selecting = False

    def show(self, anchor, compact, source, stage=None):
        if self.popover:
            self.popover.destroy()
        popup = self.popover = GlassPopover(anchor, 'settings-popover')
        popup.heading(text('Player settings', 'Настройки плеера'))
        appearance = getattr(self, 'appearance', None)
        owner = getattr(self.fullscreen, '__self__', None)
        if appearance:
            if owner:
                appearance.bind_audio(owner)
            appearance.decorate_popup(popup)

        from header_glass import GlassNavigation
        nav = Gtk.Box(spacing=2)
        nav.set_homogeneous(True)
        nav.get_style_context().add_class('menu-nav')
        self.section_buttons = {}
        for key, title in (('player', text('Player', 'Плеер')),
                           ('audio', text('Sound', 'Звук')),
                           ('appearance', text('Look', 'Вид')),
                           ('system', text('System', 'Система'))):
            button = Gtk.ToggleButton(label=title)
            button.get_style_context().add_class('menu-tab')
            button.set_has_tooltip(False)
            button.get_accessible().set_name(title)
            button.connect('clicked', lambda _b, key=key: self.select_section(key))
            nav.pack_start(button, True, True, 0)
            self.section_buttons[key] = button
        self.navigation = GlassNavigation(nav)
        self.navigation.DURATION = .52
        popup.body.pack_start(self.navigation, False, False, 0)
        if appearance:
            unsubscribe = appearance.subscribe(self.navigation.finish)
            popup.connect('destroy', lambda *_: unsubscribe())

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(220)
        self.stack.set_interpolate_size(False)
        self.stack.set_homogeneous(True)
        self.pages, self.scrolls = {}, {}
        height = max(160, min(270, popup.content_height - 176))
        for key in self.section_buttons:
            page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
            page.set_margin_end(2)
            page.set_margin_top(2)
            page.set_margin_bottom(2)
            scroll = popup.scroller(page, max_height=height)
            scroll.set_min_content_height(height)
            self.pages[key], self.scrolls[key] = page, scroll
            self.stack.add_named(scroll, key)
        popup.body.pack_start(self.stack, True, True, 0)

        def action(page, title, callback, icon='go-next-symbolic', note=None, danger=False):
            button = Gtk.Button()
            button.get_style_context().add_class('menu-action')
            if danger:
                button.get_style_context().add_class('menu-danger')
            row = Gtk.Box(spacing=10)
            image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
            image.set_pixel_size(17)
            row.pack_start(image, False, False, 0)
            titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            titles.pack_start(label(title, 'menu-section-title'), False, False, 0)
            if note:
                titles.pack_start(label(note), False, False, 0)
            row.pack_start(titles, True, True, 0)
            button.add(row)
            button.set_has_tooltip(False)
            button.get_accessible().set_name(title)
            button.connect('clicked', lambda _b: (popup.popdown(), callback()))
            self.pages[page].pack_start(button, False, False, 0)
            return button

        def desktop_action(callback):
            def run():
                if stage:
                    stage.hide()
                callback()
            return run

        if stage:
            self.fullscreen_button = action('player', text('Back to widget', 'Вернуться к виджету'), stage.dismiss,
                                            'view-restore-symbolic')
        elif self.fullscreen:
            self.fullscreen_button = action('player', text('Listening room', 'Комната прослушивания'), self.fullscreen,
                                            'view-fullscreen-symbolic', text('Open fullscreen', 'Открыть на весь экран'))
        if self.dj:
            self.dj_button = action('player', text('Ember DJ', 'Эмбер DJ'), self.dj, 'audio-input-microphone-symbolic',
                                    text('Your own radio', 'Твоё личное радио'))
        if self.accounts:
            self.accounts_button = action('player', text('Accounts & sign-in', 'Аккаунты и вход'), desktop_action(self.accounts),
                                          'avatar-default-symbolic', 'Spotify · Apple Music · YouTube · '+text('Yandex', 'Яндекс'))
        self.mode_button = action('player', text('Full player', 'Обычный режим') if compact else text('Compact player', 'Компактный режим'),
                                  desktop_action(self.compact), 'view-dual-symbolic')

        audio = self.pages['audio']
        audio.pack_start(label(text('Sound & transitions', 'Звук и переходы'), 'menu-section-title'), False, False, 0)
        flow = getattr(self, 'flow', None)
        if flow:
            from flow_control import FlowControl
            well = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            well.get_style_context().add_class('menu-well')
            switches = Gtk.Box(spacing=6)
            switches.pack_start(FlowControl(flow), True, True, 0)
            switches.pack_start(FlowControl(flow, beats=True), False, False, 0)
            well.pack_start(switches, False, False, 0)
            well.pack_start(label(flow.message), False, False, 0)
            audio.pack_start(well, False, False, 0)
        apple = getattr(owner, 'apple_web', None)
        self.scene_button = None
        if apple and getattr(owner, 'source', '') == 'apple-music' and getattr(owner, 'apple_mode', '') == 'native':
            state = apple.state.get('spatial', {})
            toggle = Gtk.CheckButton(label=text('Apple · Atmos / Lossless · beta', 'Apple · Atmos / Lossless · бета'))
            toggle.set_active(state.get('enabled') is True)
            toggle.set_has_tooltip(False)
            toggle.set_sensitive(not getattr(apple, 'spatial_preparing', False))
            toggle.connect('toggled', lambda button: (popup.popdown(), apple.set_spatial(button.get_active())))
            audio.pack_start(toggle, False, False, 3)
            audio.pack_start(label(text('Atmos soundstage and EmberFlow. Beat alignment is unavailable with Atmos.',
                                       'Сцена Atmos и EmberFlow. Подгонка битов с Atmos недоступна.')), False, False, 0)
            if state.get('enabled'):
                self.scene_button = action('audio', text('Soundstage · speakers / headphones', 'Звуковая сцена · колонки / наушники'),
                                            lambda: self.open_scene(anchor, apple, appearance), 'audio-headphones-symbolic')
                audio.reorder_child(self.scene_button, 1)
            connect = action('audio', text('Connect Apple Lossless…', 'Подключить Apple Lossless…'),
                             lambda: apple.connect_lossless(), 'network-connect-symbolic')
            connect.set_sensitive(not getattr(apple, 'lossless_connecting', False))
        else:
            audio.pack_start(label(text('EmberFlow follows the active music source. Apple soundstage controls appear here when native Apple Music is selected.',
                                       'EmberFlow работает с текущим источником. Настройки звуковой сцены доступны здесь при выборе нативного Apple Music.')), False, False, 0)

        self.build_appearance(appearance)
        system = self.pages['system']
        system.pack_start(label(text('Connections & player', 'Подключения и приложение'), 'menu-section-title'), False, False, 0)
        self.refresh_button = action('system', text('Refresh connections', 'Обновить подключения'), self.refresh, 'view-refresh-symbolic')
        self.restart_button = action('system', text('Restart player', 'Перезапустить плеер'), self.restart, 'system-reboot-symbolic')
        if self.hide:
            self.hide_button = action('system', text('Hide player', 'Скрыть плеер'), self.hide, 'window-minimize-symbolic')
        if self.quit:
            self.quit_button = action('system', text('Close player', 'Закрыть плеер'), self.quit, 'window-close-symbolic', danger=True)
        footer = Gtk.Box(spacing=7)
        footer.pack_start(label('●', 'source-status', False), False, False, 0)
        footer.pack_start(label(source, 'menu-subtitle', False), True, True, 0)
        footer.pack_end(label(text('DESKTOP', 'ПК'), 'menu-brand', False), False, False, 0)
        popup.body.pack_start(footer, False, False, 0)
        self.select_section(self.section)
        popup.present()

    def build_appearance(self, appearance):
        page = self.pages['appearance']
        page.pack_start(label(text('A different atmosphere', 'Настроение пространства'), 'menu-section-title'), False, False, 0)
        if not appearance:
            page.pack_start(label(text('Themes are available in the desktop player.', 'Темы доступны в настольном плеере.')), False, False, 0)
            return
        default_note = text('Snow is available with Winter Glow.', 'Снег доступен в рождественской теме.')

        def save_theme(value):
            if appearance.set_theme(value):
                self.appearance_note.set_text(default_note)
            else:
                sync()
                self.appearance_note.set_text(text('Could not save the theme. Your previous theme is kept.',
                                                   'Не удалось сохранить тему. Прежняя тема сохранена.'))

        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        grid.set_column_homogeneous(True)
        self.theme_cards, self.theme_toggles = {}, {}
        # Retain the public switch handles used by the desktop's live theme
        # integration; each card activates the same preference, never a copy.
        for key, attr in (('nocturne', 'night_switch'), ('mirrorball', 'mirror_switch'), ('christmas', 'theme_switch')):
            switch = Gtk.Switch()
            switch.set_active(appearance.theme == key)
            switch.connect('notify::active', lambda item, _pspec, key=key:
                           save_theme(key if item.get_active() else 'classic')
                           if item.get_active() != (appearance.theme == key) else None)
            setattr(self, attr, switch)
            self.theme_toggles[key] = switch
        themes = (('classic', text('Ember', 'Эмбер'), text('Amber & brass', 'Янтарь и латунь'), '◉'),
                  ('nocturne', text('Nocturne', 'Тёплая ночь'), text('Charcoal & quiet light', 'Уголь и тихий свет'), '☾'),
                  ('mirrorball', text('Mirror room', 'Зеркальный зал'), text('Prismatic reflections', 'Свет и преломления'), '◇'),
                  ('christmas', text('Winter Glow', 'Рождество'), text('Pine & candlelight', 'Хвоя и свет свечей'), '✦'))
        for index, (key, title, note, symbol) in enumerate(themes):
            card = Gtk.Button()
            card.get_style_context().add_class('theme-card')
            card.set_has_tooltip(False)
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            top = Gtk.Box(spacing=6)
            top.pack_start(label(symbol, 'theme-card-light', False), False, False, 0)
            top.pack_start(label(title, 'theme-card-title'), True, True, 0)
            content.pack_start(top, False, False, 0)
            content.pack_start(label(note, 'theme-card-note'), False, False, 0)
            card.add(content)
            card.get_accessible().set_name(title)
            card.connect('clicked', lambda _b, key=key: save_theme(key))
            grid.attach(card, index % 2, index // 2, 1, 1)
            self.theme_cards[key] = card
        page.pack_start(grid, False, False, 0)
        snow = Gtk.Box(spacing=10)
        snow.get_style_context().add_class('menu-well')
        snow.pack_start(label(text('Light snow', 'Лёгкий снег'), 'menu-section-title'), True, True, 0)
        self.snow_switch = Gtk.Switch()
        self.snow_switch.set_valign(Gtk.Align.CENTER)
        self.snow_switch.set_has_tooltip(False)
        self.snow_switch.get_accessible().set_name(text('Light snow', 'Лёгкий снег'))
        def save_snow(item, _pspec):
            if item.get_active() == appearance.snow_enabled:
                return
            if appearance.set_snow(item.get_active()):
                self.appearance_note.set_text(default_note)
            else:
                sync()
                self.appearance_note.set_text(text('Could not save the snow setting.', 'Не удалось сохранить настройку снега.'))
        self.snow_switch.connect('notify::active', save_snow)
        snow.pack_end(self.snow_switch, False, False, 0)
        page.pack_start(snow, False, False, 0)
        self.appearance_note = label(default_note)
        page.pack_start(self.appearance_note, False, False, 0)

        def sync():
            for key, switch in self.theme_toggles.items():
                switch.set_active(appearance.theme == key)
            for key, card in self.theme_cards.items():
                context = card.get_style_context()
                context.add_class('selected') if key == appearance.theme else context.remove_class('selected')
                card.get_accessible().set_description(text('Selected', 'Выбрано') if key == appearance.theme else '')
            self.snow_switch.set_active(appearance.snow_enabled)
            self.snow_switch.set_sensitive(appearance.christmas)
        sync()
        unsubscribe = appearance.subscribe(sync)
        page.connect('destroy', lambda *_: unsubscribe())

    def open_scene(self, anchor, apple, appearance):
        from scene_control import SceneControl
        if getattr(self, 'scene_popup', None):
            self.scene_popup.destroy()
        popup = self.scene_popup = GlassPopover(anchor, 'scene-popover', width=436)
        if appearance:
            appearance.decorate_popup(popup)
        popup.heading(text('Soundstage', 'Звуковая сцена'))
        self.scene_control = SceneControl(apple)
        # The scene has its own bounded scroller. Give it the remaining monitor
        # height, rather than trapping it inside a compact widget's allocation.
        self.scene_control.scroll.set_min_content_width(0)
        self.scene_control.scroll.set_max_content_height(max(160, popup.content_height - 120))
        popup.body.pack_start(self.scene_control, True, True, 0)
        popup.present()
