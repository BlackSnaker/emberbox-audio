"""Public YouTube search, links and queue inside the existing music card."""
import re
from gi.repository import Gtk, Pango
from source_picker import text
from discovery_panel import label, clear
from youtube_search import Search, video_url


class YouTubePanel(Gtk.Box):
    def __init__(self, artwork, play, show_status, queue):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        self.artwork, self.play_track = artwork, play
        self.show_status, self.queue = show_status, queue
        self.layout_changed = lambda: False
        self.results = []
        self.selected_id = ''
        self.search = Search(self.on_results)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_bottom(17)
        heading = label('YouTube', 'drawer-heading')
        self.pack_start(heading,False,False,0)
        caption = label(text('Music without an account', 'Музыка без аккаунта'), 'caption')
        self.pack_start(caption,False,False,0)
        row = Gtk.Box(spacing=7)
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text(text('Song, artist or YouTube link', 'Трек, исполнитель или ссылка YouTube'))
        self.entry.get_style_context().add_class('track-search')
        self.entry.connect('activate', self.submit)
        row.pack_start(self.entry,True,True,0)
        self.search_button = Gtk.Button()
        search_icon = Gtk.Image.new_from_icon_name('edit-find-symbolic', Gtk.IconSize.MENU)
        search_icon.set_pixel_size(15)
        self.search_button.add(search_icon)
        self.search_button.get_style_context().add_class('warm-button')
        self.search_button.get_accessible().set_name(text('Search YouTube','Искать на YouTube'))
        self.search_button.connect('clicked',self.submit)
        row.pack_start(self.search_button,False,False,0)
        self.pack_start(row,False,False,0)
        status = Gtk.Box(spacing=7)
        self.spinner = Gtk.Spinner()
        status.pack_start(self.spinner,False,False,0)
        self.notice = label('', 'caption')
        self.notice.set_line_wrap(True)
        self.notice.set_max_width_chars(46)
        status.pack_start(self.notice,True,True,0)
        self.pack_start(status,False,False,0)
        scroll=Gtk.ScrolledWindow()
        scroll.get_style_context().add_class('discovery-scroll')
        scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(260)
        scroll.set_max_content_height(260)
        self.content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4)
        scroll.add(self.content)
        self.pack_start(scroll,True,True,0)
        self.render(self.queue())

    def open(self):
        if not self.results:
            self.render(self.queue())

    def submit(self, _widget=None):
        query=self.entry.get_text().strip()[:300]
        if not query:
            return
        try:
            parsed=video_url(query)
        except ValueError:
            self.notice.set_text(text('Paste a link to a single video.', 'Вставь ссылку на отдельный ролик.'))
            return
        if parsed:
            self.search.cancel()
            url,start=parsed
            ident=url.rsplit('=',1)[1]
            item={'id':ident,'url':url,'title':text('Opening YouTube…','Открываю YouTube…'),'channel':'YouTube','duration':0}
            self.spinner.stop()
            self.results=[item]
            self.render(self.results)
            self.play_track(item,self.results,start)
        elif '://' in query:
            self.notice.set_text(text('Use a YouTube link or search by title.', 'Вставь ссылку YouTube или название трека.'))
        else:
            self.notice.set_text(text('Searching YouTube…','Ищу на YouTube…'))
            self.spinner.start()
            self.search.start(query)

    def on_results(self, results, error):
        self.spinner.stop()
        if error:
            self.notice.set_text(text('Search failed. Check the connection and try again.',
                                      'Не удалось выполнить поиск. Проверь соединение и повтори.'))
            return
        self.results=results
        self.notice.set_text('' if results else text('Nothing found. Try another query.','Ничего не найдено. Попробуй другой запрос.'))
        self.render(results)

    def render(self, items):
        clear(self.content)
        self.buttons=[]
        if not items:
            empty=label(text('Find a song to begin','Найди трек, чтобы начать'),'drawer-heading')
            empty.set_margin_top(45)
            self.content.pack_start(empty,False,False,0)
        for item in items:
            button=Gtk.Button()
            button.get_style_context().add_class('track-row')
            button.get_accessible().set_name(item['title'])
            row=Gtk.Box(spacing=9)
            image=Gtk.Image()
            self.artwork.load(image,f"https://i.ytimg.com/vi/{item['id']}/hqdefault.jpg",44,8)
            row.pack_start(image,False,False,0)
            info=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3)
            info.pack_start(label(item['title'],'track-title',35),False,False,0)
            info.pack_start(label(item.get('channel',''),'mix-subtitle',35),False,False,0)
            row.pack_start(info,True,True,0)
            duration=int(item.get('duration') or 0)
            row.pack_end(label(f'{duration//60}:{duration%60:02d}' if duration else 'LIVE' if item.get('live') else '',
                               'track-duration'),False,False,0)
            button.add(row)
            button.connect('clicked',lambda _b,selected=item,queue=list(items):self.play_track(selected,queue,0))
            self.content.pack_start(button,False,False,0)
            self.buttons.append((button,item['id']))
        self.content.show_all()
        self.update_current(self.selected_id)
        self.layout_changed()

    def update_current(self, ident):
        self.selected_id=ident
        for button,video in getattr(self,'buttons',[]):
            style=button.get_style_context()
            style.add_class('current-track') if ident==video else style.remove_class('current-track')

    def on_refresh(self, _widget=None):
        if self.entry.get_text().strip():
            self.submit()
        else:
            self.render(self.queue())

    def close(self):
        self.search.close()
