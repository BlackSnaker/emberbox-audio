"""A bounded glass source deck, also reachable on the compact cover."""
import os
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Pango
from glass_menu import GlassPopover

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
        popup = self.popover = GlassPopover(anchor, 'source-popover', width=376)
        appearance=getattr(anchor.get_toplevel(),'ember_appearance',None)
        if appearance:appearance.decorate_popup(popup)
        popup.heading(text('Music sources', 'Источники музыки'),
                      text('Four services. One listening space.', 'Четыре сервиса · один плеер'))
        box = popup.body

        def label(value, style, *, wrap=False):
            item=Gtk.Label(label=value)
            item.set_xalign(0)
            item.set_hexpand(True)
            item.get_style_context().add_class(style)
            if wrap:
                item.set_line_wrap(True)
                item.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                item.set_max_width_chars(24)
            return item

        def activate(callback):
            def run(_button):
                popup.popdown()
                callback()
            return run

        grid=Gtk.Grid(column_spacing=9,row_spacing=9)
        grid.set_column_homogeneous(True)
        grid.get_style_context().add_class('source-grid')
        self.service_buttons={}
        services=(('spotify','Spotify',text('Your music','Твоя музыка'),'♫'),
                  ('apple-music','Apple Music',text('Your library','Медиатека'),'♪'),
                  ('youtube','YouTube',text('Search & play','Поиск и музыка'),'▶'),
                  ('yandex-music',text('Yandex Music','Яндекс Музыка'),text('My Wave','Моя волна'),'≈'))
        for index,(key,name,detail,symbol) in enumerate(services):
            item=Gtk.Button()
            item.set_hexpand(True)
            item.set_has_tooltip(False)
            style=item.get_style_context()
            style.add_class('source-card')
            style.add_class('source-'+key)
            if source==key:style.add_class('selected')
            content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6)
            top=Gtk.Box(spacing=6)
            from service_icons import service_icon
            lamp=service_icon(key,32)
            top.pack_start(lamp,True,True,0)
            indicator=Gtk.Label(label='●' if source==key else '')
            indicator.get_style_context().add_class('source-status')
            top.pack_end(indicator,False,False,0)
            content.pack_start(top,False,False,0)
            title=label(name,'source-title',wrap=True)
            title.set_max_width_chars(18)
            content.pack_start(title,False,False,0)
            caption=label(detail,'source-detail',wrap=True)
            caption.set_max_width_chars(18)
            content.pack_start(caption,False,False,0)
            item.add(content)
            item.get_accessible().set_name(name+(text(', selected',', выбрано') if source==key else ''))
            item.get_accessible().set_description(detail+text('. Play inside Ember.','. Воспроизведение внутри Ember.'))
            item.connect('clicked',activate(lambda k=key:self.changed(k,None)))
            grid.attach(item,index%2,index//2,1,1)
            self.service_buttons[key]=item
        box.pack_start(grid,False,False,0)

        desktop=[session for session in sessions if session.name.startswith('org.mpris.MediaPlayer2.spotify')]
        browsers = [session for session in sessions if session.family]
        self.external_expander=None
        self.session_scroll=None
        self.session_buttons=[]
        if desktop or browsers:
            self.external_expander=Gtk.Expander(label=text('Other players','Другие плееры'))
            self.external_expander.get_style_context().add_class('source-connections')
            self.external_expander.set_has_tooltip(False)
            self.external_expander.get_accessible().set_description(text(
                'Optional browser sessions and the Spotify desktop client.',
                'Необязательные сеансы браузера и настольный клиент Spotify.'))
            external=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
            self.session_scroll=popup.scroller(external,max_height=min(120,max(72,popup.content_height-360)))
            self.external_expander.add(self.session_scroll)
            box.pack_start(self.external_expander,False,False,0)

        def session_button(title,detail,selected,callback):
            item=Gtk.Button()
            item.get_style_context().add_class('source-session-row')
            if selected:item.get_style_context().add_class('selected')
            content=Gtk.Box(spacing=9)
            lamp=Gtk.Label(label='●' if selected else '○')
            lamp.get_style_context().add_class('source-status')
            content.pack_start(lamp,False,False,0)
            titles=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3)
            titles.pack_start(label(title,'source-title',wrap=True),False,False,0)
            if detail:titles.pack_start(label(detail,'source-detail',wrap=True),False,False,0)
            content.pack_start(titles,True,True,0)
            item.add(content)
            item.set_has_tooltip(False)
            item.get_accessible().set_name(title+(text(', selected',', выбрано') if selected else ''))
            item.get_accessible().set_description(detail)
            item.connect('clicked',activate(callback))
            external.pack_start(item,False,False,0)
            self.session_buttons.append(item)
            return item

        for session in desktop:
            session_button(text('Spotify desktop','Клиент Spotify'),text('Optional desktop app','Необязательное приложение'),
                           source=='spotify' and binding==session.binding,
                           lambda s=session:self.changed('spotify',s))
        for session in browsers:
            site = 'youtube' if session.youtube else 'apple-music' if session.apple else 'youtube' if source == 'youtube' else 'apple-music'
            selected_binding = youtube_binding if site == 'youtube' else binding
            prefix = 'YouTube' if site == 'youtube' else 'Apple Music'
            session_button(prefix+' · '+session.identity,str(session.metadata.get('xesam:title','')),
                           source==site and selected_binding==session.binding,
                           lambda s=session,service=site:self.changed(service,s))
        if browsers:
            external.pack_start(label(text('Browser controls can affect other tabs.',
                                           'Управление браузером может затронуть другие вкладки.'),'source-detail',wrap=True),False,False,3)

        if self.accounts:
            self.accounts_button=Gtk.Button()
            self.accounts_button.get_style_context().add_class('source-footer')
            self.accounts_button.get_style_context().add_class('menu-action')
            self.accounts_button.get_style_context().add_class('menu-action')
            row=Gtk.Box(spacing=10)
            icon=Gtk.Image.new_from_icon_name('avatar-default-symbolic',Gtk.IconSize.MENU)
            icon.set_pixel_size(18)
            row.pack_start(icon,False,False,0)
            titles=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3)
            titles.pack_start(label(text('Accounts & sign-in','Аккаунты и вход'),'source-title'),False,False,0)
            titles.pack_start(label(text('Connect music services','Подключить музыкальные сервисы'),'source-detail',wrap=True),False,False,0)
            row.pack_start(titles,True,True,0)
            row.pack_end(Gtk.Label(label='›'),False,False,0)
            self.accounts_button.add(row)
            self.accounts_button.set_has_tooltip(False)
            self.accounts_button.get_accessible().set_name(text('Accounts & sign-in','Аккаунты и вход'))
            self.accounts_button.connect('clicked',activate(self.accounts))
            box.pack_start(self.accounts_button,False,False,0)
        popup.present()
