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

    def popups_for(self, window):
        for popup in (self.popover,getattr(self,'scene_popup',None)):
            anchor=popup.get_relative_to() if popup else None
            if anchor and anchor.get_toplevel() is window:yield popup

    def dismiss_for(self, window):
        for popup in tuple(self.popups_for(window)):popup.popdown()

    def is_open_for(self, window):
        return any(popup.get_mapped() for popup in self.popups_for(window))

    def show(self, anchor, compact, source, stage=None):
        if self.popover:
            self.popover.destroy()
        popup = self.popover = Gtk.Popover.new(anchor)
        popup.get_style_context().add_class('settings-popover')
        popup.set_position(Gtk.PositionType.BOTTOM)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        box.set_border_width(12)
        box.set_size_request(228, -1)
        if stage:
            scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
            scroll.set_propagate_natural_height(True)
            scroll.set_max_content_height(max(180,stage.window.get_allocated_height()-140))
            scroll.add(box);popup.add(scroll)
        else:popup.add(box)
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
            switches=Gtk.Box(spacing=6)
            switches.pack_start(FlowControl(self.flow),True,True,0)
            switches.pack_start(FlowControl(self.flow,beats=True),False,False,0)
            box.pack_start(switches,False,False,3)
            note=Gtk.Label(label=self.flow.message);note.set_line_wrap(True);note.set_max_width_chars(30)
            note.set_xalign(0);note.get_style_context().add_class('caption');box.pack_start(note,False,False,2)

        owner=getattr(self.fullscreen,'__self__',None)
        apple=getattr(owner,'apple_web',None)
        if apple and getattr(owner,'source','')=='apple-music' and getattr(owner,'apple_mode','')=='native':
            state=apple.state.get('spatial',{})
            toggle=Gtk.CheckButton(label=text('Apple · Atmos / Lossless · beta','Apple · Atmos / Lossless · бета'))
            toggle.set_active(state.get('enabled') is True);toggle.set_has_tooltip(False)
            toggle.set_sensitive(not getattr(apple,'spatial_preparing',False))
            toggle.connect('toggled',lambda button:(popup.popdown(),apple.set_spatial(button.get_active())))
            box.pack_start(toggle,False,False,3)
            note=Gtk.Label(label=text('Atmos scenes with EmberFlow. Beat alignment is unavailable in this mode.','Сцена Atmos и EmberFlow. Подгонка битов в этом режиме недоступна.'))
            note.set_line_wrap(True);note.set_max_width_chars(30);note.set_xalign(0)
            note.get_style_context().add_class('caption');box.pack_start(note,False,False,2)
            if state.get('enabled'):
                scene=Gtk.Button(label=text('Soundstage · speakers / headphones','Звуковая сцена · колонки / наушники'))
                scene.get_style_context().add_class('filter-chip')
                scene.get_style_context().add_class('settings-action');scene.set_has_tooltip(False)
                def open_scene(_button):
                    from scene_control import SceneControl
                    popup.popdown()
                    if getattr(self,'scene_popup',None):self.scene_popup.destroy()
                    self.scene_popup=Gtk.Popover.new(anchor);self.scene_popup.get_style_context().add_class('scene-popover')
                    self.scene_control=SceneControl(apple);self.scene_popup.add(self.scene_control)
                    self.scene_popup.connect('closed',lambda item:item.destroy());self.scene_popup.show_all();self.scene_popup.popup()
                scene.connect('clicked',open_scene);box.pack_start(scene,False,False,4)
            connect=Gtk.Button(label=text('Connect Apple Lossless…','Подключить Apple Lossless…'))
            connect.get_style_context().add_class('filter-chip')
            connect.set_sensitive(not getattr(apple,'lossless_connecting',False));connect.set_has_tooltip(False)
            connect.get_style_context().add_class('settings-action')
            connect.connect('clicked',lambda _button:(popup.popdown(),apple.connect_lossless()))
            box.pack_start(connect,False,False,2)

        def action(label, callback, style='filter-chip'):
            button = Gtk.Button(label=label)
            button.get_style_context().add_class(style)
            button.get_style_context().add_class('settings-action')
            button.connect('clicked', lambda _button: (popup.popdown(), callback()))
            box.pack_start(button, False, False, 0)
            return button

        def desktop_action(callback):
            def run():
                if stage:stage.hide()
                callback()
            return run

        if stage:
            self.fullscreen_button=action(text('Back to widget','Вернуться к виджету'),stage.dismiss)
        elif self.fullscreen:
            self.fullscreen_button = action(text('Listening room · Fullscreen','Комната прослушивания · На весь экран'),self.fullscreen)
        if self.dj:self.dj_button=action(text('Ember DJ · Your own radio','Ember DJ · Личное радио'),self.dj)
        if self.accounts:
            self.accounts_button = action(text('Accounts · Spotify / Apple / Yandex','Аккаунты · Spotify / Apple / Яндекс'),desktop_action(self.accounts))
        self.mode_button = action(
            text('Full player', 'Обычный режим') if compact else text('Compact player', 'Компактный режим'),
            desktop_action(self.compact))
        self.refresh_button = action(text('Refresh connections', 'Обновить подключения'), self.refresh)
        self.restart_button = action(text('Restart widget', 'Перезапустить виджет'), self.restart, 'warm-button')
        if self.hide:self.hide_button=action(text('Hide player','Скрыть плеер'),self.hide)
        if self.quit:self.quit_button=action(text('Close player','Закрыть плеер'),self.quit)
        popup.show_all()
        popup.popup()
