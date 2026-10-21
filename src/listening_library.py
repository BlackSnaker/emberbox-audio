"""Fullscreen collection and queue pages, rendered from typed music metadata."""
from datetime import datetime
from gi.repository import Gtk,Pango
from source_picker import text
from discovery_panel import clear
from listening_queue import track,LIMIT
from music_library import NAMES

CSS=b'''
.stage-nav { background-color: rgba(13,21,16,.48); border-radius: 21px; padding: 3px; }
.ember-stage button.stage-tab { background-image: none; background-color: transparent; border: none;
  border-radius: 17px; box-shadow: none; padding: 8px 14px; color: #a89984; font-size: 11px; }
.ember-stage button.stage-tab:checked { background-image: linear-gradient(to bottom right,#3a4030,#282d23);
  color: #f5d68c; box-shadow: inset 0 1px rgba(255,241,206,.05); }
.stage-library-title { color: #fbf1c7; font-weight: bold; font-size: 29px; letter-spacing: -.6px; }
.stage-library-note { color: #a89984; font-size: 11px; }
.stage-library-source { color: #d3b976; font-size: 10px; letter-spacing: 1px; }
.ember-stage entry.stage-search { background-image: none; background-color: rgba(10,18,13,.5); color: #ebdbb2;
  border: 1px solid rgba(189,174,147,.11); border-radius: 19px; padding: 10px 16px; font-size: 13px;
  box-shadow: inset 1px 2px 5px rgba(0,0,0,.16); outline-width: 0; }
.ember-stage entry.stage-search:focus { border-color: rgba(215,153,33,.4); }
.stage-library-scroll, .stage-library-scroll viewport, .stage-library-scroll flowbox { background: transparent; border: none; }
.stage-library-scroll flowboxchild { padding: 0; border: none; outline: none; background: transparent; }
.stage-library-scroll scrollbar { background: transparent; }
.stage-library-scroll scrollbar slider { background: rgba(189,174,147,.18); min-width: 4px; border-radius: 4px; }
.ember-stage button.stage-album { background-image: linear-gradient(to bottom right,rgba(48,56,42,.7),rgba(26,34,25,.7));
  border: 1px solid rgba(235,219,178,.035); border-radius: 18px; padding: 12px; box-shadow: none; }
.ember-stage button.stage-album:hover { border-color: rgba(250,189,47,.22); background-color: rgba(250,189,47,.025); }
.stage-card-title { color: #ebdbb2; font-weight: bold; font-size: 15px; }
.stage-card-subtitle { color: #a89984; font-size: 11px; }
.stage-track-row { background-color: rgba(18,26,18,.42); border-radius: 15px; padding: 3px 8px 3px 3px; }
.ember-stage button.stage-song { background: transparent; border: none; border-radius: 12px; padding: 7px 9px; box-shadow: none; }
.ember-stage button.stage-song:hover { background-color: rgba(235,219,178,.035); }
.ember-stage button.stage-add { background-image: linear-gradient(to bottom right,#353d2c,#242c21);
  color: #e2c578; border: none; border-radius: 15px; min-height: 22px; min-width: 24px; padding: 6px 9px; box-shadow: none; font-size: 15px; }
.ember-stage button.stage-add:disabled { color: #646b59; background-color: transparent; background-image: none; }
.ember-stage button.stage-accent { background-image: linear-gradient(to bottom right,#f6cf70,#cf9b37);
  color: #282b21; border: none; border-radius: 17px; padding: 9px 17px; font-size: 12px; font-weight: bold; }
.stage-row-number { color: #bc9855; font-size: 11px; }
.stage-section-label { color: #bbbd9f; font-size: 11px; font-weight: bold; letter-spacing: 1px; }
.stage-queue-current { background-image: linear-gradient(to right,rgba(88,76,40,.4),rgba(36,46,30,.6));
  border: 1px solid rgba(235,219,178,.06); border-radius: 19px; padding: 13px 18px; }
.stage-queue-empty { color: #d5d4b8; font-size: 25px; font-weight: bold; }
.ember-stage .small-screen .stage-library-title { font-size: 23px; }
'''


def label(value,style,width=0):
    item=Gtk.Label(label=str(value));item.set_xalign(0)
    item.get_style_context().add_class(style)
    if width:item.set_max_width_chars(width);item.set_ellipsize(Pango.EllipsizeMode.END)
    return item


def button(value,action,style='stage-quiet',accessible=''):
    item=Gtk.Button(label=value);item.get_style_context().add_class(style)
    item.set_has_tooltip(False);item.connect('clicked',lambda _b:action())
    if accessible:item.get_accessible().set_name(accessible)
    return item


def scroll(content):
    item=Gtk.ScrolledWindow();item.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
    item.set_overlay_scrolling(True);item.set_min_content_height(0);item.set_propagate_natural_height(False)
    item.get_style_context().add_class('stage-library-scroll');item.add(content)
    return item


def collection(item):
    return item.get('kind') in ('playlist','album','library-playlists','library-albums') or any(
        value in item.get('uri','') for value in (':album:',':playlist:',':library-albums:',':library-playlists:'))


def duration(item):
    seconds=int(item.get('duration_ms') or 0)//1000
    return f'{seconds//60}:{seconds%60:02d}' if seconds else ''


def queue_greeting():
    hour=datetime.now().hour
    if 5<=hour<12:return text('Let the morning play.','Пусть утро звучит.')
    if 12<=hour<18:return text('A soundtrack for your day.','Музыка для твоего дня.')
    if 18<=hour<23:return text('Let the evening continue.','Пусть вечер продолжается.')
    return text('Late hours, favourite songs.','Ночь — время любимых треков.')


class LibraryView(Gtk.Box):
    def __init__(self,service,artwork,accounts):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=13)
        self.service,self.artwork,self.accounts=service,artwork,accounts
        self.source=service.host.source;self.category='home';self.selected=None;self.items=[]
        self.cache={};self.next_offset=None;self.busy=False;self.active=False;self.updating=False
        self.card_size=160;self.request=0;self.song_buttons=[];self.album_buttons=[]
        hero=Gtk.Box(spacing=24);names=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        self.hero_image=Gtk.Image();self.hero_image.set_no_show_all(True);hero.pack_start(self.hero_image,False,False,0)
        self.title=label(text('A little more discovery.','Ещё немного открытий.'),'stage-library-title',35)
        self.subtitle=label('','stage-library-note',65)
        names.pack_start(self.title,False,False,0);names.pack_start(self.subtitle,False,False,0)
        hero.pack_start(names,True,True,0)
        self.entry=Gtk.SearchEntry();self.entry.set_width_chars(34);self.entry.set_max_length(200)
        self.entry.get_style_context().add_class('stage-search');self.entry.set_valign(Gtk.Align.CENTER)
        self.entry.set_placeholder_text(text('Song, artist or album','Трек, исполнитель, альбом'))
        for p in (Gtk.EntryIconPosition.PRIMARY,Gtk.EntryIconPosition.SECONDARY):self.entry.set_icon_tooltip_text(p,None)
        self.entry.connect('activate',lambda _e:self.search())
        hero.pack_end(self.entry,False,False,0);self.pack_start(hero,False,False,0)
        filters=Gtk.Box(spacing=7);self.tabs={}
        for key,name in [('home',text('For you','Подборки')),('albums',text('Albums','Альбомы')),('search',text('Search','Поиск'))]:
            b=Gtk.ToggleButton(label=name);b.get_style_context().add_class('stage-tab');b.set_has_tooltip(False)
            b.connect('clicked',lambda _b,k=key:self.select(k));self.tabs[key]=b;filters.pack_start(b,False,False,0)
        self.source_badge=label('','stage-library-source');filters.pack_start(self.source_badge,True,True,14)
        self.spinner=Gtk.Spinner();filters.pack_start(self.spinner,False,False,0)
        self.refresh_button=button('↻',lambda:self.load(refresh=True),accessible=text('Refresh collection','Обновить коллекцию'))
        filters.pack_end(self.refresh_button,False,False,0);self.pack_start(filters,False,False,0)
        self.context=Gtk.Box(spacing=9);self.context.set_no_show_all(True)
        self.back_button=button('‹ '+text('Collections','Коллекции'),self.back)
        self.play_all_button=button('▶ '+text('Play','Слушать'),lambda:self.service.play_all(self.songs()),'stage-add')
        self.play_all_button.get_style_context().add_class('stage-accent')
        self.add_all_button=button('+ '+text('Add tracks','Добавить треки'),lambda:self.add(self.songs()))
        self.context.pack_start(self.back_button,False,False,0)
        self.context.pack_end(self.add_all_button,False,False,0);self.context.pack_end(self.play_all_button,False,False,0)
        for child in self.context.get_children():child.show_all()
        self.pack_start(self.context,False,False,0)
        self.content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=9)
        self.scroll=scroll(self.content);self.pack_start(self.scroll,True,True,0)
        foot=Gtk.Box(spacing=12);self.notice=label('','stage-library-note',95)
        self.notice.set_line_wrap(True);self.notice.set_lines(2)
        foot.pack_start(self.notice,True,True,0)
        self.connect_button=button(text('Accounts','Аккаунты'),accounts)
        self.connect_button.set_no_show_all(True);foot.pack_end(self.connect_button,False,False,0)
        self.wave_button=button('≈ '+text('My Wave','Моя волна'),self.wave,'stage-add')
        self.wave_button.set_no_show_all(True);foot.pack_end(self.wave_button,False,False,0)
        self.pack_end(foot,False,False,0)
        self.unsubscribe=service.subscribe(self.service_changed)
        self.show_all();self.context.hide();self.connect_button.hide();self.wave_button.hide();self.sync_tabs()

    def sync_tabs(self):
        self.updating=True
        for key,b in self.tabs.items():b.set_active(key==self.category)
        self.updating=False

    def activate(self):
        self.active=True
        if self.source!=self.service.host.source:
            self.source=self.service.host.source;self.selected=None;self.items=[];self.category='home';self.sync_tabs()
            self.next_offset=None;self.render()
        self.source_badge.set_text(NAMES[self.source].upper())
        self.wave_button.set_visible(self.source=='yandex-music')
        self.load()

    def deactivate(self):
        self.active=False;self.request+=1;self.busy=False;self.spinner.stop();self.service.cancel_browse()

    def select(self,category):
        if self.updating:return
        self.category=category;self.selected=None;self.sync_tabs()
        if category=='search':
            self.entry.grab_focus()
            if not self.entry.get_text().strip():
                self.items=[];self.next_offset=None;self.render();return
        self.load()

    def search(self):
        if not self.entry.get_text().strip():return
        self.category='search';self.selected=None;self.sync_tabs();self.load(refresh=True)

    def key(self):return self.source,self.category,self.entry.get_text().strip() if self.category=='search' else '',(self.selected or {}).get('uri') or (self.selected or {}).get('id') or ''

    def load(self,refresh=False,append=False):
        if not self.active:return
        key=self.key()
        if self.category=='search' and not key[2] and not self.selected:
            self.items=[];self.next_offset=None;self.render();return
        if not refresh and not append and key in self.cache:
            self.items,self.next_offset,note=self.cache[key];self.render();self.notice.set_text(note);return
        self.request+=1;request=self.request
        self.busy=True;self.spinner.start();self.notice.set_text(text('Finding your music…','Ищу твою музыку…'))
        self.connect_button.hide()
        def done(result,error):
            if not self.active or request!=self.request or key!=self.key():return
            self.busy=False;self.spinner.stop()
            if error:
                self.notice.set_text(str(error));self.connect_button.show();return
            values=result.get('tracks',result.get('items',[]))
            self.items=(self.items if append else [])+values
            self.items=self.items[:LIMIT];self.next_offset=result.get('next') if len(self.items)<LIMIT else None
            note=result.get('note','')
            if result.get('total',len(self.items))>len(self.items) and self.next_offset is None:
                note=text(f"Showing {len(self.items)} of {result['total']} loaded tracks",f"Показано треков: {len(self.items)} из {result['total']}")
            elif result.get('next') is not None and len(self.items)>=LIMIT:
                note=text(f'Showing the first {LIMIT} tracks',f'Показаны первые {LIMIT} треков')
            self.cache[key]=(list(self.items),self.next_offset,note)
            self.render();self.notice.set_text(note)
        self.service.load(self.category,done,term=key[2],collection=self.selected,offset=self.next_offset or 0 if append else 0)

    def open_collection(self,item):
        self.selected=item;self.load();self.scroll.get_vadjustment().set_value(0)

    def back(self):self.selected=None;self.load()

    def songs(self):return [v for v in self.items if not collection(v) and track(v,self.source)]

    def add(self,items):
        count=self.service.add(items)
        self.notice.set_text(text(f'Added {count} to your queue',f'В очередь добавлено: {count}') if count else
                             text('Queue is full or these tracks cannot be queued.', 'Очередь заполнена или эти треки нельзя добавить.'))

    def wave(self):
        self.service.stop();self.service.host.start_yandex_wave()

    def render(self):
        clear(self.content);self.song_buttons=[];self.album_buttons=[]
        if self.selected:
            self.artwork.load(self.hero_image,self.selected.get('image',''),68,10);self.hero_image.show()
            self.title.set_text(self.selected['title']);self.subtitle.set_text(self.selected.get('artist') or self.selected.get('subtitle') or NAMES[self.source])
            self.context.show();count=len(self.songs());self.add_all_button.set_label('+ '+text(f'Queue {count}',f'В очередь · {count}'))
            self.play_all_button.set_label('▶ '+text(f'Play {count}',f'Слушать · {count}'))
            self.play_all_button.set_sensitive(bool(count));self.add_all_button.set_sensitive(bool(count))
        else:
            self.hero_image.hide()
            self.context.hide()
            headings={'home':(text('A little more discovery.','Ещё немного открытий.'),text('Collections from your connected source','Подборки из подключённого источника')),
                'albums':(text('Give an album its evening.','Вечер для целого альбома.'),text('Open a cover. Stay for the whole story.','Открой обложку. Послушай историю целиком.')),
                'search':(text('Find your next favourite.','Найди свой следующий трек.'),text('Search the selected source','Поиск в выбранном источнике'))}
            title,note=headings[self.category];self.title.set_text(title);self.subtitle.set_text(note)
        collections=[i for i in self.items if collection(i)]
        if collections:
            flow=Gtk.FlowBox();flow.set_selection_mode(Gtk.SelectionMode.NONE);flow.set_homogeneous(True)
            flow.set_min_children_per_line(1);flow.set_max_children_per_line(6)
            flow.set_column_spacing(16);flow.set_row_spacing(16);flow.set_valign(Gtk.Align.START)
            for item in collections:
                b=button('',lambda value=item:self.open_collection(value),'stage-album',item['title'])
                box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=7)
                image=Gtk.Image();image.set_halign(Gtk.Align.CENTER);self.artwork.load(image,item.get('image',''),self.card_size,12)
                box.pack_start(image,False,False,0)
                name=label(item['title'],'stage-card-title',22);name.set_line_wrap(True);name.set_lines(2)
                box.pack_start(name,False,False,0)
                box.pack_start(label(item.get('subtitle') or item.get('artist') or text('Open collection','Открыть коллекцию'),'stage-card-subtitle',24),False,False,0)
                b.remove(b.get_child());b.add(box);flow.add(b);self.album_buttons.append((b,item))
            self.content.pack_start(flow,False,False,0)
        tracks=[i for i in self.items if not collection(i)]
        if tracks and collections:self.content.pack_start(label(text('TRACKS','ТРЕКИ'),'stage-section-label'),False,False,10)
        for index,item in enumerate(tracks):
            row=Gtk.Box(spacing=10);row.get_style_context().add_class('stage-track-row')
            play=button('',lambda value=item:self.service.play_now(value),'stage-song',text('Play ','Слушать ')+item.get('title',''))
            box=Gtk.Box(spacing=12)
            number=label(f'{index+1:02}','stage-row-number');number.set_size_request(22,-1);box.pack_start(number,False,False,0)
            image=Gtk.Image();self.artwork.load(image,item.get('image',''),45,7);box.pack_start(image,False,False,0)
            names=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4)
            names.pack_start(label(item.get('title',''),'stage-card-title',52),False,False,0)
            names.pack_start(label(item.get('artist') or item.get('subtitle',''),'stage-card-subtitle',55),False,False,0)
            box.pack_start(names,True,True,0);play.remove(play.get_child());play.add(box)
            row.pack_start(play,True,True,0);row.pack_start(label(duration(item),'stage-card-subtitle'),False,False,0)
            add=button('+',lambda value=item:self.add([value]),'stage-add',text('Add to queue: ','Добавить в очередь: ')+item.get('title',''))
            valid=bool(track(item,self.source));play.set_sensitive(valid);add.set_sensitive(valid)
            row.pack_end(add,False,False,0);self.content.pack_start(row,False,False,0)
            self.song_buttons.append((play,add,item))
        if not self.items:
            empty=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);empty.set_margin_top(25)
            empty.pack_start(label('✦','stage-queue-empty'),False,False,0)
            empty.pack_start(label(text('Music is one search away.','Музыка начинается с поиска.'),'stage-queue-empty',55),False,False,0)
            empty.pack_start(label(text('Enter a name above or refresh your collections.','Введи название выше или обнови подборки.'),'stage-library-note',85),False,False,0)
            self.content.pack_start(empty,False,False,0)
        if self.next_offset is not None:
            more=button(text('Load more','Загрузить ещё'),lambda:self.load(append=True))
            more.set_halign(Gtk.Align.CENTER);self.content.pack_start(more,False,False,8)
        self.content.show_all()

    def service_changed(self):
        if self.active and self.service.error:self.notice.set_text(self.service.error)

    def close(self):self.deactivate();self.unsubscribe()


class QueueView(Gtk.Box):
    def __init__(self,service,artwork):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=14)
        self.service,self.artwork=service,artwork;self.active=False;self.rows=[];self.key=None
        hero=Gtk.Box(spacing=15);names=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        self.title=label(queue_greeting(),'stage-library-title',40)
        names.pack_start(self.title,False,False,0)
        self.subtitle=label('','stage-library-note',80);names.pack_start(self.subtitle,False,False,0)
        hero.pack_start(names,True,True,0)
        self.clear_button=button(text('Clear upcoming','Очистить далее'),self.clear)
        self.play_button=button('▶ '+text('Play queue','Слушать очередь'),lambda:service.start(),'stage-add')
        self.play_button.get_style_context().add_class('stage-accent')
        hero.pack_end(self.play_button,False,False,0);hero.pack_end(self.clear_button,False,False,0)
        self.pack_start(hero,False,False,0)
        self.current=Gtk.Box(spacing=14);self.current.get_style_context().add_class('stage-queue-current')
        self.current_image=Gtk.Image();self.current.pack_start(self.current_image,False,False,0)
        current_names=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        self.current_status=label('','stage-library-source');self.current_title=label('','stage-card-title',75)
        self.current_artist=label('','stage-card-subtitle',85)
        for v in (self.current_status,self.current_title,self.current_artist):current_names.pack_start(v,False,False,0)
        self.current.pack_start(current_names,True,True,0);self.pack_start(self.current,False,False,0)
        self.content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        self.scroll=scroll(self.content);self.pack_start(self.scroll,True,True,0)
        self.notice=label('','stage-library-note',95);self.notice.set_line_wrap(True);self.pack_end(self.notice,False,False,0)
        self.unsubscribe=service.subscribe(self.changed)
        self.show_all()

    def activate(self):self.active=True;self.render(force=True)
    def deactivate(self):self.active=False
    def changed(self):
        if self.active:self.render()
    def clear(self):self.service.book.clear(self.service.host.source);self.service.changed()
    def edit(self,index,direction):
        book=self.service.book;source=self.service.host.source
        book.remove(source,index) if direction==0 else book.move(source,index,direction)
        self.service.changed()

    def render(self,force=False):
        greeting=queue_greeting()
        if self.title.get_text()!=greeting:self.title.set_text(greeting)
        h=self.service.host;book=self.service.book;source=h.source
        title,artist=h.title.get_text(),h.artist.get_text()
        key=book.revision,source,title,artist,h.art_url,h.playing,self.service.loading,self.service.error,book.active
        if key==self.key and not force:return
        self.key=key;pending=book.upcoming(source)
        self.subtitle.set_text(NAMES[source]+' · '+text(f'{len(pending)} up next',f'Далее: {len(pending)}')+' · '+text('Saved on this device','Сохраняется на этом устройстве'))
        self.current_status.set_text(text('STARTING…','ЗАПУСКАЮ…') if self.service.loading else text('NOW PLAYING','СЕЙЧАС ИГРАЕТ') if h.playing else text('CURRENT TRACK','ТЕКУЩИЙ ТРЕК'))
        self.current_title.set_text(title);self.current_artist.set_text(artist)
        self.artwork.load(self.current_image,h.art_url or '',58,9)
        running=book.active==source
        self.play_button.set_label(text('Playing in order','Играет по порядку') if running and h.playing else
                                   '▶ '+text('Play queue','Слушать очередь'))
        self.play_button.set_sensitive(bool(pending or self.service.error) and not self.service.loading and not (running and h.playing))
        self.clear_button.set_sensitive(bool(pending));self.notice.set_text(self.service.error)
        clear(self.content);self.rows=[]
        for number,(index,item) in enumerate(pending):
            row=Gtk.Box(spacing=8);row.get_style_context().add_class('stage-track-row')
            play=button('',lambda i=index:self.service.start(i),'stage-song',text('Play ','Слушать ')+item['title'])
            names=Gtk.Box(spacing=12);n=label(f'{number+1:02}','stage-row-number');n.set_size_request(22,-1)
            names.pack_start(n,False,False,0);image=Gtk.Image();self.artwork.load(image,item.get('image',''),42,7);names.pack_start(image,False,False,0)
            info=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4)
            info.pack_start(label(item['title'],'stage-card-title',60),False,False,0)
            info.pack_start(label(item['artist'],'stage-card-subtitle',65),False,False,0)
            names.pack_start(info,True,True,0);play.remove(play.get_child());play.add(names);row.pack_start(play,True,True,0)
            row.pack_start(label(duration(item),'stage-card-subtitle'),False,False,6)
            up=button('↑',lambda i=index:self.edit(i,-1),'stage-add',text('Move up','Выше'))
            down=button('↓',lambda i=index:self.edit(i,1),'stage-add',text('Move down','Ниже'))
            remove=button('×',lambda i=index:self.edit(i,0),'stage-add',text('Remove from queue','Убрать из очереди'))
            up.set_sensitive(number>0);down.set_sensitive(number<len(pending)-1)
            for v in (up,down,remove):row.pack_start(v,False,False,0)
            self.content.pack_start(row,False,False,0);self.rows.append((play,up,down,remove,item))
        if not pending:
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.set_margin_top(25)
            box.pack_start(label('＋','stage-queue-empty'),False,False,0)
            box.pack_start(label(text('Make room for your favourites.','Здесь будут твои следующие песни.'),'stage-queue-empty',65),False,False,0)
            box.pack_start(label(text('Use + beside a track in Collection. Adding never interrupts playback.',
                'Нажимай + у треков в Коллекции. Добавление не прерывает музыку.'),'stage-library-note',95),False,False,0)
            self.content.pack_start(box,False,False,0)
        self.content.show_all()

    def close(self):self.unsubscribe()
