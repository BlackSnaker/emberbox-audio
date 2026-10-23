"""An in-room artist journal: portrait, discography, release notes and tracks."""
import time
from gi.repository import Gtk,Pango,GdkPixbuf
from source_picker import text
from listening_library import label,button,scroll,duration
from listening_queue import track
from discovery_panel import clear
from music_library import NAMES
from artist_catalog import artist_ref,plain,SECTIONS
from artist_header import ArtistBanner,BannerCache

CSS=b'''
.stage-artist-hero { background-image: linear-gradient(to bottom right,rgba(76,73,49,.6),rgba(28,35,26,.55));
  border: 1px solid rgba(235,219,178,.045); border-radius: 28px; padding: 24px;
  box-shadow: inset 0 1px rgba(251,241,199,.045); }
.stage-artist-banner { background-image: linear-gradient(to bottom right,#414431,#232d23); border-radius: 28px; }
.stage-artist-hero.stage-artist-banner-content { background-image: none; background-color: transparent; border: none; box-shadow: none; }
.stage-artist-name { color: #fbf1c7; font-size: 44px; font-weight: bold; letter-spacing: -1px; }
.stage-artist-kicker { color: #d4b568; font-size: 9px; letter-spacing: 2px; }
.stage-artist-summary { color: #bdae93; font-size: 12px; }
.stage-artist-prose { color: #d5c7a7; font-size: 15px; }
.stage-artist-reading { background-color: rgba(15,23,16,.38); border-radius: 22px; padding: 22px 26px; }
.stage-artist-empty { color: #bdae93; font-size: 16px; }
.ember-stage button.stage-artist-link { background: transparent; border: none; box-shadow: none;
  padding: 2px 0; color: #bdae93; border-radius: 6px; }
.ember-stage button.stage-artist-link:hover { color: #f5d68c; }
.ember-stage button.stage-artist-link:hover label { color: #f5d68c; }
.ember-stage button.stage-artist-filter { padding: 7px 12px; font-size: 11px; }
.stage-artist-section { color: #ebdbb2; font-size: 19px; font-weight: bold; }
.stage-artist-credit { color: #928374; font-size: 10px; }
.ember-stage .small-screen .stage-artist-name { font-size: 30px; }
.ember-stage .small-screen .stage-artist-hero { padding: 16px; border-radius: 22px; }
.ember-stage .small-screen .stage-artist-prose { font-size: 13px; }
.stage-artist-hero.stage-artist-mini { padding: 12px 16px; }
.ember-stage .stage-artist-mini .stage-artist-name { font-size: 26px; }
.ember-stage .stage-artist-mini button.stage-accent, .ember-stage .stage-artist-mini button.stage-quiet { padding: 6px 12px; min-height: 16px; }
'''

NAMES_SECTION={
    'overview':('Overview','Обзор'),'albums':('Albums','Альбомы'),
    'singles':('Singles & EPs','Синглы и EP'),'compilations':('Compilations','Сборники'),
    'appears':('Appears on','Участия'),'about':('About','Об артисте'),
    'latest-release':('Releases in the spotlight','В центре внимания'),
    'top-songs':('Popular songs','Популярные песни')}


def paragraph(value,style='stage-artist-prose'):
    result=label(plain(value),style);result.set_line_wrap(True)
    result.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR);result.set_max_width_chars(82)
    result.set_selectable(True);result.set_hexpand(True)
    return result


class ArtistView(Gtk.Box):
    def __init__(self,service,artwork,back,accounts,search):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        self.service,self.artwork,self.go_back,self.accounts,self.search=service,artwork,back,accounts,search
        self.active=False;self.closed=False;self.request=0;self.source=service.host.source
        self.reference={};self.profile=None;self.release=None;self.release_ref=None
        self.section='overview';self.items=[];self.sections=[];self.choices=[];self.next_offset=None
        self.cache={};self.card_size=164;self.portrait_size=184;self.busy=False;self.syncing=False
        self.banner_cache=BannerCache(artwork.pool)
        self.saved_section='overview';self.note='';self.size=None
        self.song_buttons=[];self.album_buttons=[];self.choice_buttons=[];self.filters={}
        toolbar=Gtk.Box(spacing=12)
        self.back_button=button('‹ '+text('Back','Назад'),self.back)
        toolbar.pack_start(self.back_button,False,False,0)
        self.crumb=label(text('THE ARTIST ROOM','КОМНАТА АРТИСТА'),'stage-artist-kicker')
        toolbar.pack_start(self.crumb,True,True,0)
        self.spinner=Gtk.Spinner();toolbar.pack_end(self.spinner,False,False,0)
        self.refresh_button=button('↻',self.refresh,accessible=text('Refresh artist','Обновить артиста'))
        toolbar.pack_end(self.refresh_button,False,False,0)
        self.pack_start(toolbar,False,False,0)
        self.filter_bar=Gtk.Box(spacing=3);self.filter_bar.get_style_context().add_class('stage-nav')
        self.filter_bar.set_halign(Gtk.Align.START);self.filter_bar.set_no_show_all(True)
        self.pack_start(self.filter_bar,False,False,0)
        self.content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=22)
        self.scroll=scroll(self.content);self.pack_start(self.scroll,True,True,0)
        foot=Gtk.Box(spacing=12)
        self.notice=label('','stage-library-note');self.notice.set_line_wrap(True);self.notice.set_lines(2)
        self.notice.set_ellipsize(Pango.EllipsizeMode.END);foot.pack_start(self.notice,True,True,0)
        self.accounts_button=button(text('Accounts','Аккаунты'),accounts)
        self.accounts_button.set_no_show_all(True);foot.pack_end(self.accounts_button,False,False,0)
        self.pack_end(foot,False,False,0)
        self.unsubscribe=service.subscribe(self.changed)
        self.show_all();self.accounts_button.hide();self.filter_bar.hide()

    def set_reference(self,ref):
        self.request+=1;self.reference=dict(ref);self.source=self.service.host.source
        self.profile=self.release=self.release_ref=None;self.items=[];self.sections=[];self.choices=[]
        self.section='overview';self.next_offset=None;self.note=''

    def activate(self):
        self.active=True
        if self.source!=self.service.host.source:self.set_reference(artist_ref(self.service.host))
        if not self.reference:self.reference=artist_ref(self.service.host)
        if self.profile:self.render()
        else:self.load('artist',self.reference)

    def deactivate(self):
        self.active=False;self.request+=1;self.busy=False;self.spinner.stop();self.service.cancel_browse()

    def back(self):
        if self.release_ref:
            self.request+=1;self.service.cancel_browse();self.busy=False;self.spinner.stop()
            self.release=self.release_ref=None;self.section=self.saved_section;self.select(self.section,force=True)
        else:self.go_back()

    def refresh(self):
        if self.release_ref:self.load('release',self.release_ref,refresh=True)
        elif self.section in ('overview','about'):self.load('artist',self.reference,refresh=True)
        else:self.load('artist-section',dict(self.reference,section=self.section),refresh=True)

    def select(self,section,force=False):
        if self.syncing:return
        if not force and section==self.section:
            self.syncing=True
            for key,b in self.filters.items():b.set_active(key==section)
            self.syncing=False;return
        self.section=section;self.release=self.release_ref=None;self.items=[];self.next_offset=None
        if section in ('overview','about'):
            self.request+=1;self.service.cancel_browse();self.busy=False;self.spinner.stop();self.render()
        else:self.load('artist-section',dict(self.reference,section=section))

    def choose(self,ref):
        self.set_reference({'id':str(ref['id']),'name':str(ref.get('name') or '')});self.load('artist',self.reference)

    def open_release(self,value):
        self.saved_section=self.section;self.release_ref=dict(value);self.release=dict(value)
        self.items=[];self.next_offset=None;self.load('release',self.release_ref)

    def load(self,category,ref,append=False,refresh=False):
        if self.closed or not self.active:return
        self.request+=1;generation=self.request;source=self.source
        offset=self.next_offset or 0 if append else 0
        key=(source,category,str(ref.get('id') or ''),str(ref.get('songId') or ref.get('songUri') or ''),
             str(ref.get('name') or ''),str(ref.get('section') or ''),offset)
        self.busy=True;self.spinner.start();self.accounts_button.hide()
        self.notice.set_text(text('Opening a little more of their world…','Открываю музыкальный мир артиста…'))
        self.render()
        def done(result,error):
            if self.closed or not self.active or generation!=self.request or source!=self.service.host.source:return
            self.busy=False;self.spinner.stop()
            if error:
                self.notice.set_text(str(error)[:350]);self.accounts_button.show();self.render();return
            result=result or {};self.cache[key]=(time.monotonic(),result)
            while len(self.cache)>24:self.cache.pop(next(iter(self.cache)))
            self.note=str(result.get('note') or '')[:450];self.choices=result.get('choices') or []
            if category=='artist':
                self.profile=result.get('artist');self.sections=result.get('sections') or []
                if self.profile and self.profile.get('id'):
                    self.reference={'id':str(self.profile['id']),'name':self.profile.get('name','')}
                self.search_only=bool(result.get('searchOnly'))
            elif category=='release':self.release=result.get('release') or self.release
            values=result.get('items') or []
            if append:
                seen={v.get('uri') or v.get('id') for v in self.items}
                self.items.extend(v for v in values if (v.get('uri') or v.get('id')) not in seen)
            else:self.items=list(values)
            self.items=self.items[:200]
            self.next_offset=result.get('next') if len(self.items)<200 else None
            self.render();self.notice.set_text(self.note)
            if not append:self.scroll.get_vadjustment().set_value(0)
        cached=self.cache.get(key)
        if not refresh and cached and time.monotonic()-cached[0]<900:
            done(cached[1],None);return
        self.service.load(category,done,collection=ref,offset=offset)

    def songs(self):
        values=self.items if self.release_ref else next((s.get('items',[]) for s in self.sections if s.get('id')=='top-songs'),[])
        return [v for v in values if track(v,self.source)]

    def add(self,values):
        count=self.service.add(values)
        self.notice.set_text(text(f'Added {count} to your queue',f'В очередь добавлено: {count}'))

    def changed(self):
        if self.active and self.service.error:self.notice.set_text(self.service.error)

    def hero(self,value,release=False):
        shell=Gtk.Box(spacing=24);shell.get_style_context().add_class('stage-artist-hero')
        if self.portrait_size<128:shell.get_style_context().add_class('stage-artist-mini')
        image=Gtk.Image();image.set_valign(Gtk.Align.START)
        image.set_size_request(self.portrait_size,self.portrait_size)
        shell.pack_start(image,False,False,0)
        names=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=9);names.set_valign(Gtk.Align.CENTER);names.set_hexpand(True)
        if self.portrait_size<128:names.set_spacing(5)
        names.pack_start(label(NAMES[self.source].upper()+'  /  '+text('RELEASE' if release else 'ARTIST','РЕЛИЗ' if release else 'АРТИСТ'),'stage-artist-kicker'),False,False,0)
        title=label(value.get('title') if release else value.get('name') or self.reference.get('name',''),'stage-artist-name',32)
        title.set_line_wrap(True);title.set_lines(2);names.pack_start(title,False,False,0)
        meta=[]
        if release:
            meta=[value.get('artist') or (self.profile or {}).get('name',''),str(value.get('releaseDate') or '')[:10]]
            if value.get('trackCount'):meta.append(text(f"{value['trackCount']} tracks",f"Треков: {value['trackCount']}"))
        else:meta=value.get('genres') or []
        summary=label('  ·  '.join(v for v in meta if v),'stage-artist-summary',80)
        summary.set_line_wrap(True);names.pack_start(summary,False,False,0)
        controls=Gtk.Box(spacing=9);songs=self.songs()
        self.play_all_button=button('▶ '+text('Listen','Слушать'),lambda:self.service.play_all(self.songs()),'stage-accent')
        self.add_all_button=button('+ '+text('Queue','В очередь'),lambda:self.add(self.songs()))
        self.play_all_button.set_sensitive(bool(songs));self.add_all_button.set_sensitive(bool(songs))
        controls.pack_start(self.play_all_button,False,False,0);controls.pack_start(self.add_all_button,False,False,0)
        if not release:
            read=button(text('Their story','Об артисте')+'  ›',lambda:self.select('about'))
            controls.pack_start(read,False,False,0)
        names.pack_start(controls,False,False,3);shell.pack_start(names,True,True,0)
        if release:
            self.artwork.load(image,value.get('image',''),self.portrait_size,24,high_quality=True)
            self.content.pack_start(shell,False,False,0)
        else:
            banner=ArtistBanner(shell,value.get('image',''),self.banner_cache,152 if self.portrait_size<128 else 242)
            size=self.portrait_size
            def photo(pixels):
                if not banner.closed and pixels:
                    image.set_from_pixbuf(pixels.scale_simple(size,size,GdkPixbuf.InterpType.BILINEAR));banner.set_photo(pixels)
            self.artwork.load(banner.source_image,value.get('image',''),600,24,high_quality=True,on_loaded=photo)
            self.content.pack_start(banner,False,False,0)

    def render(self):
        clear(self.content);clear(self.filter_bar);self.filter_bar.hide()
        self.song_buttons=[];self.album_buttons=[];self.choice_buttons=[];self.filters={}
        if self.release_ref:
            self.back_button.set_label('‹ '+text('Artist','Артист'));self.hero(self.release or self.release_ref,True)
            prose=(self.release or {}).get('description') or ''
            if prose:
                reveal=Gtk.Revealer();reveal.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN);reveal.set_transition_duration(350)
                reading=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);reading.get_style_context().add_class('stage-artist-reading')
                reading.pack_start(paragraph(prose),False,False,0)
                reading.pack_start(paragraph((self.release or {}).get('copyright') or '', 'stage-artist-credit'),False,False,0)
                reveal.add(reading)
                self.read_button=button(text('Read the liner notes','Прочесть об альбоме')+'  ⌄',lambda:reveal.set_reveal_child(not reveal.get_reveal_child()))
                self.content.pack_start(self.read_button,False,False,0);self.content.pack_start(reveal,False,False,0)
            self.track_rows(self.items)
        elif self.profile:
            self.back_button.set_label('‹ '+text('Back','Назад'));self.hero(self.profile)
            if getattr(self,'search_only',False):
                self.content.pack_start(paragraph(self.note),False,False,0)
                self.content.pack_start(button(text('Search this name','Найти это имя'),lambda:self.search(self.profile.get('name','')),'stage-accent'),False,False,0)
            else:
                tabs=self.filter_bar
                for section in SECTIONS:
                    b=Gtk.ToggleButton(label=text(*NAMES_SECTION[section]));b.get_style_context().add_class('stage-tab');b.get_style_context().add_class('stage-artist-filter')
                    b.set_has_tooltip(False);b.set_active(section==self.section);b.connect('clicked',lambda _b,s=section:self.select(s))
                    tabs.pack_start(b,False,False,0);self.filters[section]=b
                for child in tabs.get_children():child.show_all()
                tabs.show()
                if self.section=='about':
                    reading=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14);reading.get_style_context().add_class('stage-artist-reading')
                    reading.pack_start(label(text('Behind the music','За музыкой'),'stage-artist-section'),False,False,0)
                    reading.pack_start(paragraph(self.profile.get('bio') or text('This source has not supplied an artist description.',
                        'Источник пока не передал описание артиста.')),False,False,0)
                    reading.pack_start(label(NAMES[self.source]+' · '+text('Artist editorial information','Информация об артисте'),'stage-artist-credit'),False,False,0)
                    self.content.pack_start(reading,False,False,0)
                elif self.section=='overview':
                    for section in self.sections:
                        values=section.get('items') or []
                        if not values:continue
                        self.content.pack_start(label(text(*NAMES_SECTION.get(section['id'],('Music','Музыка'))),'stage-artist-section'),False,False,0)
                        self.track_rows(values[:8]) if section['id']=='top-songs' else self.cards(values[:8])
                    if not any(s.get('items') for s in self.sections) and not self.busy:self.empty()
                elif self.items:self.cards(self.items)
                elif not self.busy:self.empty()
        elif self.choices:
            self.content.pack_start(label(text('Whose world shall we open?','Чей мир откроем?'),'stage-library-title'),False,False,0)
            self.content.pack_start(paragraph(text('Choose an artist. Collaborations and namesakes stay separate.',
                'Выбери исполнителя. Участники совместного трека и тёзки показаны отдельно.')),False,False,0)
            self.cards(self.choices,choices=True)
        else:
            self.content.pack_start(label(self.reference.get('name') or text('Artist','Артист'),'stage-artist-name',40),False,False,0)
            self.content.pack_start(paragraph(text('Gathering the portrait, releases and stories…','Собираю портрет, релизы и истории…') if self.busy else
                text('No artist was returned. Try another recording or refresh.', 'Артист не найден. Попробуй другой трек или обнови страницу.')),False,False,0)
        if self.next_offset is not None:
            category='release' if self.release_ref else 'artist-section'
            ref=self.release_ref or dict(self.reference,section=self.section)
            more=button(text('Load more','Загрузить ещё'),lambda:self.load(category,ref,append=True))
            more.set_sensitive(not self.busy);self.content.pack_start(more,False,False,0)
        self.content.show_all()

    def empty(self):
        self.content.pack_start(paragraph(text('No releases supplied in this section. Explore another chapter.',
            'В этом разделе источник не передал релизы. Загляни в другую главу.'),'stage-artist-empty'),False,False,18)

    def cards(self,values,choices=False):
        flow=Gtk.FlowBox();flow.set_selection_mode(Gtk.SelectionMode.NONE);flow.set_homogeneous(True)
        flow.set_min_children_per_line(1);flow.set_max_children_per_line(6);flow.set_column_spacing(16);flow.set_row_spacing(16)
        for value in values:
            title=str(value.get('name') if choices else value.get('title') or '')
            b=button('',lambda v=value:self.choose(v) if choices else self.open_release(v),'stage-album',title)
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
            image=Gtk.Image();image.set_halign(Gtk.Align.CENTER)
            self.artwork.load(image,value.get('image',''),self.card_size,24 if choices else 12,high_quality=True)
            box.pack_start(image,False,False,0)
            title_label=label(title,'stage-card-title',22);title_label.set_line_wrap(True);title_label.set_lines(2)
            box.pack_start(title_label,False,False,0)
            meta=str(value.get('releaseDate') or '')[:4] or value.get('subtitle') or text('Open artist' if choices else 'Explore the release','Открыть артиста' if choices else 'Открыть релиз')
            box.pack_start(label(meta,'stage-card-subtitle',24),False,False,0)
            b.remove(b.get_child());b.add(box);flow.add(b)
            (self.choice_buttons if choices else self.album_buttons).append((b,value))
        self.content.pack_start(flow,False,False,0)

    def track_rows(self,values):
        context=tuple(v for v in values if track(v,self.source))
        for i,value in enumerate(values):
            row=Gtk.Box(spacing=10);row.get_style_context().add_class('stage-track-row')
            row.pack_start(label(f'{i+1:02}','stage-row-number'),False,False,9)
            image=Gtk.Image();self.artwork.load(image,value.get('image',''),42,7);row.pack_start(image,False,False,0)
            names=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=1)
            play=button(value.get('title',''),lambda v=value:self.service.play_now(v,context=context),'stage-song')
            play.get_child().set_xalign(0);play.get_child().set_ellipsize(Pango.EllipsizeMode.END);play.get_child().set_max_width_chars(65)
            play.get_style_context().add_class('stage-card-title');names.pack_start(play,False,False,0)
            names.pack_start(label(value.get('artist',''),'stage-card-subtitle',65),False,False,5)
            row.pack_start(names,True,True,0);row.pack_start(label(duration(value),'stage-card-subtitle'),False,False,0)
            add=button('+',lambda v=value:self.add([v]),'stage-add',text('Add to queue: ','В очередь: ')+value.get('title',''))
            valid=bool(track(value,self.source));play.set_sensitive(valid);add.set_sensitive(valid)
            row.pack_end(add,False,False,0);self.content.pack_start(row,False,False,0);self.song_buttons.append((play,add,value))

    def resize(self,width,height):
        size=(max(118,min(200,(width-160)//6-28)),88 if height<680 else 128 if height<800 else 184)
        if self.size==size:return
        self.size=size;self.card_size,self.portrait_size=size
        if self.active:self.render()

    def close(self):
        self.deactivate();self.closed=True;self.unsubscribe();self.cache.clear();self.banner_cache.clear()
