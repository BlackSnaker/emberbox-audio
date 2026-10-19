"""A compact in-player account centre in the same warm tactile materials."""
from gi.repository import Gtk
from source_picker import text


def label(value,style):
    item = Gtk.Label(label=value)
    item.set_xalign(0)
    item.set_line_wrap(True)
    item.set_max_width_chars(43)
    item.get_style_context().add_class(style)
    return item


class AccountPanel(Gtk.Box):
    def __init__(self,accounts,back,parent,layout_changed):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        self.accounts,self.parent,self.layout_changed = accounts,parent,layout_changed
        self.cards = {}
        self.previous = {}
        self.set_margin_start(18);self.set_margin_end(18);self.set_margin_bottom(18)
        heading = Gtk.Box(spacing=9)
        button = Gtk.Button(label='‹')
        button.get_style_context().add_class('mini-button')
        button.get_accessible().set_name(text('Back to music','Вернуться к музыке'))
        button.connect('clicked',lambda _b:back())
        heading.pack_start(button,False,False,0)
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3)
        titles.pack_start(label(text('Your music accounts','Твои музыкальные аккаунты'),'drawer-heading'),False,False,0)
        titles.pack_start(label(text('Connect once. Keep your music close.','Подключи один раз — музыка всегда рядом.'),'caption'),False,False,0)
        heading.pack_start(titles,True,True,0)
        self.pack_start(heading,False,False,2)
        for source,title in (('spotify','Spotify'),('apple-music','Apple Music'),*([('yandex-music',text('Yandex Music','Яндекс Музыка'))] if accounts.yandex else [])):
            self._card(source,title)
        self.pack_start(label(text('Sign-in opens in the service’s own window. Return here when you’re done.',
                                  'Вход откроется в окне сервиса. После него возвращайся сюда.'),'caption'),False,False,2)
        self.show_all()
        self.update()

    def _card(self,source,title):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        card.get_style_context().add_class('account-card')
        row = Gtk.Box(spacing=8)
        dot = label('●',{'spotify':'account-spotify','apple-music':'account-apple','yandex-music':'account-yandex'}[source])
        row.pack_start(dot,False,False,0)
        row.pack_start(label(title,'account-title'),True,True,0)
        spinner = Gtk.Spinner();spinner.set_no_show_all(True);row.pack_start(spinner,False,False,0)
        status = label('','account-status');row.pack_end(status,False,False,0)
        card.pack_start(row,False,False,0)
        description = label('','caption');card.pack_start(description,False,False,0)
        actions = Gtk.Box(spacing=8)
        connect = Gtk.Button();connect.get_style_context().add_class('warm-button')
        connect.connect('clicked',lambda _b:self.accounts.connect(source))
        actions.pack_start(connect,True,True,0)
        listen = Gtk.Button(label=text('Listen','Слушать'))
        listen.set_no_show_all(True)
        listen.get_style_context().add_class('filter-chip')
        listen.connect('clicked',lambda _b:self.accounts.listen(source))
        actions.pack_start(listen,False,False,0)
        card.pack_start(actions,False,False,0)
        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6)
        details.set_no_show_all(True)
        if source == 'spotify':
            picks = Gtk.Button(label=text('Connect personal picks','Подключить личные подборки'))
            picks.get_style_context().add_class('filter-chip')
            picks.connect('clicked',lambda _b:self.accounts.open_picks())
            details.pack_start(picks,False,False,0)
            details.pack_start(label(text('May restart Spotify once to enable your collections.',
                'Для подключения подборок Spotify может один раз перезапуститься.'),'caption'),False,False,0)
        else:
            for key,caption in (('runtime',text('Choose playback engine…','Выбрать движок…')),
                                ('module',text('Choose Widevine folder…','Выбрать папку Widevine…'))):
                choose = Gtk.Button(label=caption)
                choose.get_style_context().add_class('filter-chip')
                choose.connect('clicked',lambda _b,k=key,s=source:self.choose_file(k,s))
                details.pack_start(choose,False,False,0)
        card.pack_start(details,False,False,0)
        self.cards[source] = dict(status=status,description=description,connect=connect,listen=listen,
                                  details=details,spinner=spinner)
        self.pack_start(card,False,False,0)

    def choose_file(self,key,source='apple-music'):
        dialog = Gtk.FileChooserDialog(title=text('Music playback setup','Настройка воспроизведения'),
            transient_for=self.parent(),action=Gtk.FileChooserAction.OPEN if key=='runtime' else Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons(text('Cancel','Отмена'),Gtk.ResponseType.CANCEL,text('Choose','Выбрать'),Gtk.ResponseType.OK)
        if dialog.run() == Gtk.ResponseType.OK:
            setattr(self.accounts,key,dialog.get_filename())
            self.accounts.error = ''
            self.accounts.error_source = source
            self.accounts.connect(source)
        dialog.destroy()

    def open(self):
        self.accounts.refresh()
        self.update()

    def on_refresh(self,_button):
        self.open()

    def update(self):
        changed = False
        for source,card in self.cards.items():
            state = self.accounts.state(source)
            if state == self.previous.get(source):
                continue
            self.previous[source] = state
            changed = True
            card['status'].set_text(('✓  ' if state['ready'] else '')+state['status'])
            card['description'].set_text(state['description'])
            card['connect'].set_label(state['button'])
            card['connect'].set_sensitive(not state['busy'])
            card['listen'].set_visible(state['ready'])
            card['spinner'].set_visible(state['busy'])
            card['spinner'].start() if state['busy'] else card['spinner'].stop()
            if state['details'] or (source=='spotify' and state['ready']):
                for child in card['details'].get_children():
                    child.show_all()
                card['details'].show()
            else:
                card['details'].hide()
        if changed:
            self.layout_changed()
