"""An in-room artist journal: portrait, discography, release notes and tracks."""
import time
from gi.repository import Gtk,Pango,GdkPixbuf,GLib
from source_picker import text
from listening_library import label,button,scroll,duration
from listening_queue import track
from discovery_panel import clear
from music_library import NAMES
from artist_catalog import artist_ref,plain,SECTIONS,ReleaseCatalog
from artist_header import ArtistBanner,BannerCache,portrait_slot
from artist_reveal import ArtistReveal

CSS=b'''
.stage-artist-hero { background-image: linear-gradient(to bottom right,rgba(76,73,49,.6),rgba(28,35,26,.55));
  border: 1px solid rgba(235,219,178,.045); border-radius: 28px; padding: 24px;
  box-shadow: inset 0 1px rgba(251,241,199,.045); }
.stage-artist-banner { background-image: linear-gradient(to bottom right,#414431,#232d23); border-radius: 28px; }
.stage-artist-banner.stage-artist-capture { background-image: none; background-color: transparent; }
.stage-artist-hero.stage-artist-banner-content { background-image: none; background-color: transparent; border: none; box-shadow: none; }
.stage-artist-name { color: #fbf1c7; font-size: 60px; font-weight: bold; letter-spacing: -1.8px; }
.stage-artist-name.stage-artist-long { font-size: 40px; letter-spacing: -1px; }
.stage-artist-name.stage-artist-display { font-size: 104px; letter-spacing: -3.5px; }
.stage-artist-name.stage-artist-display-medium { font-size: 88px; letter-spacing: -2.7px; }
.stage-artist-name.stage-artist-display-long { font-size: 64px; letter-spacing: -1.8px; }
.stage-artist-hero.stage-artist-banner-content { padding: 36px 40px; }
.stage-artist-banner-content .stage-artist-chip { font-size: 11px; padding: 5px 11px; }
.ember-stage .stage-artist-banner-content button.stage-quiet,
.ember-stage .stage-artist-banner-content button.stage-accent { font-size: 13px; padding: 11px 20px; border-radius: 23px; }
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
.stage-artist-chip { color: #d8c491; font-size: 10px; border: 1px solid rgba(235,219,178,.09); border-radius: 12px; padding: 4px 9px; background-color: rgba(16,23,16,.28); }
.stage-overview-panel { background-image: linear-gradient(to bottom right,rgba(48,54,39,.86),rgba(25,34,25,.8));
  border: 1px solid rgba(235,219,178,.055); border-radius: 23px; padding: 16px 18px;
  box-shadow: inset 0 1px rgba(251,241,199,.04); }
.stage-feature-title { color: #fbf1c7; font-size: 25px; font-weight: bold; letter-spacing: -.5px; }
.stage-feature-caption { color: #bdae93; font-size: 11px; }
.stage-feature-action { color: #e7bf6b; font-size: 11px; font-weight: bold; }
.stage-overview-story { color: #cabc9e; font-size: 14px; }
.stage-overview-panel .stage-track-row { background-color: rgba(14,23,15,.3); border-radius: 12px; padding: 1px 5px; }
.ember-stage button.stage-feature-button { background: transparent; border: none; box-shadow: none; padding: 0; border-radius: 14px; }
.ember-stage button.stage-feature-button:hover { background-color: rgba(235,219,178,.025); }
.ember-stage button.stage-song-compact { font-size: 13px; padding: 3px 5px; min-height: 14px; }
.ember-stage button.stage-add-compact { min-height: 16px; min-width: 18px; padding: 3px 6px; font-size: 13px; }
.stage-release-type { color: #bba77b; font-size: 9px; letter-spacing: .6px; }
.ember-stage .small-screen .stage-artist-name { font-size: 30px; }
.ember-stage .small-screen .stage-artist-hero { padding: 16px; border-radius: 22px; }
.ember-stage .small-screen .stage-artist-prose { font-size: 13px; }
.stage-artist-hero.stage-artist-mini { padding: 12px 16px; }
.ember-stage .stage-artist-mini .stage-artist-name { font-size: 26px; }
.ember-stage .stage-artist-mini button.stage-accent, .ember-stage .stage-artist-mini button.stage-quiet { padding: 6px 12px; min-height: 16px; }
.ember-stage .small-screen .stage-artist-display,
.ember-stage .small-screen .stage-artist-display-medium,
.ember-stage .small-screen .stage-artist-display-long { font-size: 40px; letter-spacing: -1px; }
.ember-stage .small-screen .stage-artist-banner-content { padding: 20px 24px; }
.ember-stage .small-screen .stage-artist-banner-content button.stage-quiet,
.ember-stage .small-screen .stage-artist-banner-content button.stage-accent { font-size: 11px; padding: 8px 13px; }
.ember-stage .stage-artist-mini .stage-artist-display,
.ember-stage .stage-artist-mini .stage-artist-display-medium,
.ember-stage .stage-artist-mini .stage-artist-display-long { font-size: 34px; }
.ember-stage .stage-artist-mini.stage-artist-banner-content { padding: 16px 20px; }
.ember-stage .stage-artist-mini .stage-artist-chip { font-size: 10px; padding: 4px 8px; }
'''

NAMES_SECTION={
    'overview':('Overview','Обзор'),'discography':('All releases','Все релизы'),'albums':('Albums','Альбомы'),
    'singles':('Singles & EPs','Синглы и EP'),'compilations':('Compilations','Сборники'),
    'appears':('Appears on','Участия'),'about':('About','Об артисте'),
    'latest-release':('Releases in the spotlight','В центре внимания'),
    'top-songs':('Popular songs','Популярные песни'),
    'featured-albums':('Essential releases','Главные релизы')}


def paragraph(value,style='stage-artist-prose'):
    result=label(plain(value),style);result.set_line_wrap(True)
    result.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR);result.set_max_width_chars(82)
    result.set_selectable(True);result.set_hexpand(True)
    return result


def masthead_height(height):
    return 360 if height>=900 else 320 if height>=800 else 248 if height>=680 else 212


class ArtistView(Gtk.Box):
    def __init__(self,service,artwork,back,accounts,search):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        self.service,self.artwork,self.go_back,self.accounts,self.search=service,artwork,back,accounts,search
        self.active=False;self.closed=False;self.request=0;self.source=service.host.source
        self.reference={};self.profile=None;self.release=None;self.release_ref=None
        self.section='overview';self.items=[];self.sections=[];self.choices=[];self.next_offset=None
        self.cache={};self.card_size=164;self.portrait_size=184;self.busy=False;self.syncing=False
        self.banner_cache=BannerCache(artwork.pool)
        self.intro_pending=False;self.render_queued=False
        self.saved_section='overview';self.note='';self.size=None
        self.catalog=ReleaseCatalog();self.card_page=0;self.card_page_size=48
        self.wide=True;self.height=1080;self.overview_panels={};self.shelf_widgets=[]
        self.overview_columns=None;self.overview_fit_key=None;self.overview_fit_idle=0
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
        toolbar.pack_start(self.filter_bar,False,False,0)
        self.content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=18)
        self.scroll=scroll(self.content);self.entrance=ArtistReveal(self.scroll,self.finish_intro)
        self.scroll.connect('size-allocate',self.queue_overview_fit)
        self.pack_start(self.entrance,True,True,0)
        foot=Gtk.Box(spacing=12)
        self.notice=label('','stage-library-note');self.notice.set_line_wrap(True);self.notice.set_lines(2)
        self.notice.set_ellipsize(Pango.EllipsizeMode.END);foot.pack_start(self.notice,True,True,0)
        self.accounts_button=button(text('Accounts','Аккаунты'),accounts)
        self.accounts_button.set_no_show_all(True);foot.pack_end(self.accounts_button,False,False,0)
        self.pack_end(foot,False,False,0)
        self.unsubscribe=service.subscribe(self.changed)
        self.show_all();self.accounts_button.hide();self.filter_bar.hide()

    def set_reference(self,ref):
        self.cancel_intro()
        self.intro_pending=True
        self.request+=1;self.reference=dict(ref);self.source=self.service.host.source
        self.profile=self.release=self.release_ref=None;self.items=[];self.sections=[];self.choices=[]
        self.section='overview';self.next_offset=None;self.note=''
        self.catalog=ReleaseCatalog();self.card_page=0;self.search_only=False

    def activate(self):
        self.active=True
        self.intro_pending=True
        if self.source!=self.service.host.source:self.set_reference(artist_ref(self.service.host))
        if not self.reference:self.reference=artist_ref(self.service.host)
        if self.profile:
            self.render()
            if self.catalog_mode():self.load_catalog()
        else:self.load('artist',self.reference)

    def deactivate(self):
        self.cancel_intro()
        self.active=False;self.request+=1;self.busy=False;self.spinner.stop();self.service.cancel_browse()

    def cancel_intro(self):
        self.intro_pending=False;self.render_queued=False;self.entrance.finish()

    def finish_intro(self):
        if self.render_queued and self.active and not self.closed:
            self.render_queued=False;self.render()

    def back(self):
        self.cancel_intro()
        if self.release_ref:
            self.request+=1;self.service.cancel_browse();self.busy=False;self.spinner.stop()
            self.release=self.release_ref=None;self.section=self.saved_section;self.select(self.section,force=True)
        else:self.go_back()

    def refresh(self):
        self.cancel_intro()
        if self.release_ref:self.load('release',self.release_ref,refresh=True)
        elif self.source=='apple-music' and self.section!='appears':
            self.catalog=ReleaseCatalog();self.card_page=0;self.load('artist',self.reference,refresh=True)
        elif self.section in ('overview','about'):self.load('artist',self.reference,refresh=True)
        else:self.load('artist-section',dict(self.reference,section=self.section),refresh=True)

    def select(self,section,force=False):
        if self.syncing:return
        if not force and section==self.section:
            self.syncing=True
            for key,b in self.filters.items():b.set_active(key==section)
            self.syncing=False;return
        self.cancel_intro()
        self.section=section;self.release=self.release_ref=None;self.items=[];self.next_offset=None;self.card_page=0
        if self.catalog_mode():
            self.request+=1;self.service.cancel_browse();self.busy=False;self.spinner.stop()
            self.items=self.catalog_selection();self.render();self.catalog_notice();self.load_catalog();return
        if section in ('overview','about'):
            self.request+=1;self.service.cancel_browse();self.busy=False;self.spinner.stop();self.render()
        else:self.load('artist-section',dict(self.reference,section=section))

    def choose(self,ref):
        self.set_reference({'id':str(ref['id']),'name':str(ref.get('name') or '')});self.load('artist',self.reference)

    def open_release(self,value):
        self.cancel_intro()
        self.saved_section=self.section;self.release_ref=dict(value);self.release=dict(value)
        self.items=[];self.next_offset=None;self.card_page=0;self.load('release',self.release_ref)

    def catalog_mode(self):
        return self.source=='apple-music' and not self.release_ref and self.section in ('overview','discography','albums','singles','compilations')

    def catalog_selection(self):
        singles={v.get('id') for v in self.section_items('singles')}
        return self.catalog.selection(self.section,singles)

    def catalog_notice(self):
        count=len(self.catalog.items)
        if self.catalog.error:
            value=text(f'{count} releases loaded · Loading interrupted. Retry to continue.',
                f'Загружено релизов: {count} · Загрузка прервалась. Можно продолжить.')
        elif self.catalog.complete:
            value=text(f'All {count} releases supplied by Apple Music · {self.catalog.storefront.upper()}',
                f'Все релизы каталога Apple Music: {count} · {self.catalog.storefront.upper()}')
        else:
            value=text(f'Loading the complete discography… {count} releases',f'Загружаю полную дискографию… Релизов: {count}')
        self.notice.set_text(value)

    def load_catalog(self):
        """One page per worker job: transport and GTK can run between pages."""
        if self.closed or not self.active or self.busy or not self.catalog_mode() or self.catalog.complete or not (self.profile or {}).get('id'):return False
        self.request+=1;generation=self.request;source=self.source;offset=self.catalog.offset
        catalog=self.catalog;catalog.error='';self.busy=True;self.spinner.start();self.catalog_notice()
        ref=dict(self.reference,section='discography')
        if catalog.storefront:ref['storefront']=catalog.storefront
        def done(result,error):
            if self.closed or not self.active or generation!=self.request or source!=self.service.host.source:return
            self.busy=False;self.spinner.stop()
            if not error:
                try:catalog.accept(result or {},offset)
                except (ValueError,TypeError) as exc:error=exc
            if error:catalog.error=str(error)[:350]
            # Refresh only the small overview shelves, preserving top songs and
            # appearances. The complete list is retained independently of GTK.
            if not error:
                single_ids={v.get('id') for v in self.section_items('singles')}
                for name in ('albums','singles','compilations'):
                    values=catalog.selection(name,single_ids)
                    existing=next((s for s in self.sections if s.get('id')==name),None)
                    if existing is None:self.sections.append({'id':name,'items':values[:6]})
                    elif values or catalog.complete:existing.update(items=values[:6],unavailable=False)
                if self.section!='overview':self.items=self.catalog_selection()
            position=self.scroll.get_vadjustment().get_value();self.render();self.catalog_notice()
            def continue_scan():
                if generation!=self.request or not self.active or self.closed:return False
                self.scroll.get_vadjustment().set_value(position)
                if not error and not catalog.complete:self.load_catalog()
                return False
            GLib.timeout_add(100,continue_scan)
        self.service.load('artist-section',done,collection=ref,offset=offset)
        return False

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
            if not self.note and any(section.get('unavailable') for section in result.get('sections') or []):
                self.note=text('Some catalogue sections did not respond. Available music is ready; refresh to retry.',
                    'Часть каталога не ответила. Доступную музыку уже можно слушать; обнови для повтора.')
            if category=='artist':
                self.profile=result.get('artist');self.sections=result.get('sections') or []
                self.catalog.single_ids.update(v.get('id') for v in self.section_items('singles') if v.get('id'))
                if self.profile and self.profile.get('id'):
                    self.reference={'id':str(self.profile['id']),'name':self.profile.get('name','')}
                self.search_only=bool(result.get('searchOnly'))
            elif category=='release':self.release=result.get('release') or self.release
            values=result.get('items') or []
            if append:
                seen={v.get('uri') or v.get('id') for v in self.items}
                for value in values:
                    ident=value.get('uri') or value.get('id')
                    if ident and ident not in seen:seen.add(ident);self.items.append(value)
            else:self.items=list(values)
            self.next_offset=result.get('next')
            self.render();self.notice.set_text(self.note)
            if not append:self.scroll.get_vadjustment().set_value(0)
            if category=='artist' and self.catalog_mode():self.load_catalog()
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
        if release:shell.pack_start(image,False,False,0)
        names=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=9);names.set_valign(Gtk.Align.CENTER);names.set_hexpand(True)
        if self.portrait_size<128:names.set_spacing(5)
        names.pack_start(label(NAMES[self.source].upper()+'  /  '+text('RELEASE' if release else 'ARTIST','РЕЛИЗ' if release else 'АРТИСТ'),'stage-artist-kicker'),False,False,0)
        name=value.get('title') if release else value.get('name') or self.reference.get('name','')
        title=label(name,'stage-artist-name',28)
        if len(str(name))>28 or release:title.get_style_context().add_class('stage-artist-long')
        if not release:
            title.get_style_context().add_class('stage-artist-display-long' if len(str(name))>16 else
                'stage-artist-display-medium' if len(str(name))>8 else 'stage-artist-display')
        title.set_line_wrap(True);title.set_lines(2);names.pack_start(title,False,False,0)
        meta=[]
        if release:
            meta=[value.get('artist') or (self.profile or {}).get('name',''),str(value.get('releaseDate') or '')[:10]]
            if value.get('trackCount'):meta.append(text(f"{value['trackCount']} "+('track' if value['trackCount']==1 else 'tracks'),f"Треков: {value['trackCount']}"))
        if release:
            summary=label('  ·  '.join(v for v in meta if v),'stage-artist-summary',80)
            summary.set_line_wrap(True);names.pack_start(summary,False,False,0)
        else:
            chips=Gtk.Box(spacing=7)
            for genre in (value.get('genres') or [])[:3]:chips.pack_start(label(genre,'stage-artist-chip',24),False,False,0)
            count=len(self.catalog.items) if self.catalog.pages else len(self.release_catalog())
            if count:
                caption=text(f'{count} releases',f'Релизов: {count}') if self.catalog.pages else text(f'{count} in this overview',f'Релизов в обзоре: {count}')
                chips.pack_start(label(caption,'stage-artist-chip'),False,False,0)
            names.pack_start(chips,False,False,0)
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
            height=masthead_height(self.height)
            if len(str(name))>28:height+=24
            banner=ArtistBanner(shell,value.get('image',''),self.banner_cache,height)
            self.hero_banner=banner
            def photo(pixels):
                if not banner.closed and pixels:banner.set_photo(pixels)
            if value.get('image'):
                self.artwork.load(banner.source_image,value['image'],1000,0,high_quality=True,keep_aspect=True,on_loaded=photo)
            self.content.pack_start(banner,False,False,0)

    def section_items(self,key):
        return next((section.get('items') or [] for section in self.sections if section.get('id')==key),[])

    def release_catalog(self):
        values=[];seen=set()
        for section in self.sections:
            if section.get('id')=='top-songs':continue
            for item in section.get('items') or []:
                key=item.get('uri') or item.get('id')
                if key and key not in seen:seen.add(key);values.append(item)
        return values

    def panel(self):
        item=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=11)
        item.get_style_context().add_class('stage-overview-panel');item.set_hexpand(True)
        return item

    def feature(self,value):
        panel=self.panel();panel.set_size_request(390 if self.wide else -1,-1)
        panel.pack_start(label(text('A RELEASE TO STEP INTO','ПОГРУЗИСЬ В РЕЛИЗ'),'stage-artist-kicker'),False,False,0)
        b=button('',lambda:self.open_release(value),'stage-feature-button',value.get('title',''))
        box=Gtk.Box(spacing=19);cover=Gtk.Image();cover.set_valign(Gtk.Align.CENTER)
        size=148 if self.wide else 108
        self.artwork.load(cover,value.get('image',''),size,15,high_quality=True);box.pack_start(cover,False,False,0)
        words=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=9);words.set_hexpand(True);words.set_valign(Gtk.Align.CENTER)
        title=label(value.get('title',''),'stage-feature-title',24);title.set_line_wrap(True);title.set_lines(2)
        words.pack_start(title,False,False,0)
        meta=[]
        if value.get('releaseDate'):meta.append(str(value['releaseDate'])[:4])
        if value.get('isCompilation'):meta.append(text('Compilation','Сборник'))
        elif value.get('isSingle'):meta.append(text('Single','Сингл'))
        elif value.get('trackCount'):meta.append(text(f"{value['trackCount']} "+('track' if value['trackCount']==1 else 'tracks'),f"Треков: {value['trackCount']}"))
        if not meta and value.get('subtitle'):meta.append(value['subtitle'])
        words.pack_start(label('  ·  '.join(meta),'stage-feature-caption',36),False,False,0)
        description=plain(value.get('description'),170)
        if description:
            teaser=label(description,'stage-feature-caption',40);teaser.set_line_wrap(True);teaser.set_lines(2)
            words.pack_start(teaser,False,False,0)
        words.pack_start(label(text('Open the release','Открыть релиз')+'  ›','stage-feature-action'),False,False,6)
        box.pack_start(words,True,True,0);b.remove(b.get_child());b.add(box);panel.pack_start(b,True,True,0)
        self.album_buttons.append((b,value));return panel

    def story(self):
        panel=self.panel();bio=plain((self.profile or {}).get('bio'),400)
        panel.pack_start(label(text('BEHIND THE SOUND','ЗА ЭТИМ ЗВУКОМ'),'stage-artist-kicker'),False,False,0)
        title=text('A little closer to the artist.','Чуть ближе к артисту.') if bio else text('There is more to explore.','Продолжим знакомство.')
        panel.pack_start(label(title,'stage-artist-section',40),False,False,0)
        prose=paragraph(bio or text('Explore albums, singles and collaborations from the connected source.',
            'Открой альбомы, синглы и совместные записи в подключённом источнике.'),'stage-overview-story')
        prose.set_lines(5);prose.set_ellipsize(Pango.EllipsizeMode.END);panel.pack_start(prose,True,True,0)
        action=button(text('Read their story','Читать об артисте')+'  ›',lambda:self.select('about'),'stage-artist-link')
        action.set_halign(Gtk.Align.START);panel.pack_start(action,False,False,0)
        return panel

    def overview(self):
        self.overview_panels={};self.shelf_widgets=[]
        releases=self.release_catalog();songs=self.section_items('top-songs')
        latest=self.section_items('latest-release')
        feature=latest[0] if latest else releases[0] if releases else None
        columns=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL if self.wide else Gtk.Orientation.VERTICAL,spacing=18)
        used=set()
        if feature:
            panel=self.feature(feature);columns.pack_start(panel,True,True,0);self.overview_panels['feature']=panel
            used.add(feature.get('uri') or feature.get('id'))
        if songs:
            panel=self.panel();heading=Gtk.Box(spacing=16)
            heading.pack_start(label(text('Start with these songs','Начни с этих песен'),'stage-artist-section',32),True,True,0)
            play=button(text('Play all','Слушать всё'),lambda:self.service.play_all(self.songs()),'stage-artist-link')
            heading.pack_end(play,False,False,0);panel.pack_start(heading,False,False,0)
            self.track_rows(songs[:4],container=panel,compact=True)
            columns.pack_start(panel,True,True,0);self.overview_panels['songs']=panel
        elif self.profile:
            panel=self.story();columns.pack_start(panel,True,True,0);self.overview_panels['story']=panel
        if columns.get_children():
            self.overview_columns=columns;self.content.pack_start(columns,False,False,0)
        for key in ('albums','featured-albums','singles','compilations','appears','latest-release'):
            values=[]
            for value in self.section_items(key):
                ident=value.get('uri') or value.get('id')
                if ident and ident not in used:used.add(ident);values.append(value)
            if not values:continue
            shelf=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=11)
            heading=Gtk.Box(spacing=16);heading.pack_start(label(text(*NAMES_SECTION[key]),'stage-artist-section'),True,True,0)
            if key in ('albums','singles','compilations','appears'):
                heading.pack_end(button(text('See all','Все релизы')+'  ›',lambda k=key:self.select(k),'stage-artist-link'),False,False,0)
            shelf.pack_start(heading,False,False,0);self.cards(values[:6],container=shelf)
            self.content.pack_start(shelf,False,False,0);self.shelf_widgets.append(shelf)
        if not releases and not songs and not self.busy:
            self.notice.set_text(text('This source has not supplied releases yet. Try Albums or Singles.',
                'Источник пока не передал релизы. Попробуй разделы «Альбомы» и «Синглы».'))

    def render(self):
        if self.entrance.busy:
            self.render_queued=True;return
        animate=False
        if self.intro_pending and self.profile and not self.release_ref:
            self.intro_pending=False;animate=self.entrance.hold_loading()
        clear(self.content);clear(self.filter_bar);self.filter_bar.hide()
        self.song_buttons=[];self.album_buttons=[];self.choice_buttons=[];self.filters={}
        self.overview_panels={};self.shelf_widgets=[]
        self.overview_columns=None;self.overview_fit_key=None
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
                    if section=='discography' and self.source!='apple-music':continue
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
                    self.overview()
                elif self.items:self.paged_cards(self.items)
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
        if self.catalog_mode() and self.catalog.error:
            retry=button(text('Continue loading the discography','Продолжить загрузку дискографии'),self.load_catalog)
            retry.set_sensitive(not self.busy);self.content.pack_start(retry,False,False,0)
        self.content.show_all()
        self.fit_overview()
        if animate:self.entrance.begin(self.hero_banner)

    def queue_overview_fit(self,*_args):
        if not self.closed and not self.overview_fit_idle:
            self.overview_fit_idle=GLib.idle_add(self.fit_overview_idle,priority=GLib.PRIORITY_DEFAULT)

    def fit_overview_idle(self):
        self.overview_fit_idle=0
        return self.fit_overview()

    def fit_overview(self):
        columns=self.overview_columns
        if (self.closed or not self.active or not self.wide or self.height<900 or
                not columns or not self.shelf_widgets):return False
        width,height=self.scroll.get_allocated_width(),self.scroll.get_allocated_height()
        if width<100 or height<100:return False
        banner=self.hero_banner
        reading_width=width-portrait_slot(width,banner.minimum_height) if banner.uri else width
        hero_height=max(banner.minimum_height,banner.content.get_preferred_height_for_width(reading_width)[1])
        heading=self.shelf_widgets[0].get_children()[0]
        heading_height=heading.get_preferred_height_for_width(width)[1]
        key=(id(columns),width,height,hero_height,heading_height)
        if key==self.overview_fit_key:return False
        self.overview_fit_key=key
        budget=height-hero_height-2*self.content.get_spacing()-heading_height-4
        panels=columns.get_children()
        panel_width=max(1,(width-columns.get_spacing()*(len(panels)-1))//len(panels))
        # Preserve the full-size portrait, typography and covers. Only tighten
        # internal gaps enough to introduce the discography within the viewport.
        for spacing in range(11,3,-1):
            for panel in panels:panel.set_spacing(spacing)
            if max(panel.get_preferred_height_for_width(panel_width)[1] for panel in panels)<=budget:break
        return False

    def paged_cards(self,values):
        # A large discography must not create hundreds of images/widgets on
        # every page arrival. All metadata is available; show 48 covers at once.
        pages=max(1,(len(values)+self.card_page_size-1)//self.card_page_size)
        self.card_page=min(self.card_page,pages-1)
        start=self.card_page*self.card_page_size;end=min(len(values),start+self.card_page_size)
        bar=Gtk.Box(spacing=12)
        bar.pack_start(label(text(f'Releases {start+1}–{end} of {len(values)}',f'Релизы {start+1}–{end} из {len(values)}'),'stage-artist-summary'),True,True,0)
        if pages>1:
            def turn(delta):
                self.card_page+=delta;self.render();self.scroll.get_vadjustment().set_value(0)
            prev=button('‹',lambda:turn(-1),accessible=text('Previous releases','Предыдущие релизы'))
            after=button('›',lambda:turn(1),accessible=text('Next releases','Следующие релизы'))
            prev.set_sensitive(self.card_page>0);after.set_sensitive(self.card_page<pages-1)
            bar.pack_start(prev,False,False,0);bar.pack_start(label(f'{self.card_page+1} / {pages}','stage-artist-summary'),False,False,0);bar.pack_start(after,False,False,0)
            self.catalog_next_button=after;self.catalog_prev_button=prev
        self.content.pack_start(bar,False,False,0);self.cards(values[start:end])

    def empty(self):
        self.content.pack_start(paragraph(text('No releases supplied in this section. Explore another chapter.',
            'В этом разделе источник не передал релизы. Загляни в другую главу.'),'stage-artist-empty'),False,False,18)

    def cards(self,values,choices=False,container=None):
        flow=Gtk.FlowBox();flow.set_selection_mode(Gtk.SelectionMode.NONE);flow.set_homogeneous(True)
        flow.set_min_children_per_line(1);flow.set_max_children_per_line(min(8,max(1,len(values))));flow.set_column_spacing(14);flow.set_row_spacing(14)
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
            if value.get('isSingle'):meta+='  ·  '+text('SINGLE','СИНГЛ')
            elif value.get('isCompilation'):meta+='  ·  '+text('COMPILATION','СБОРНИК')
            box.pack_start(label(meta,'stage-card-subtitle' if choices else 'stage-release-type',24),False,False,0)
            b.remove(b.get_child());b.add(box);flow.add(b)
            (self.choice_buttons if choices else self.album_buttons).append((b,value))
        (container if container is not None else self.content).pack_start(flow,False,False,0)

    def track_rows(self,values,container=None,compact=False):
        context=tuple(v for v in values if track(v,self.source))
        for i,value in enumerate(values):
            row=Gtk.Box(spacing=10);row.get_style_context().add_class('stage-track-row')
            row.pack_start(label(f'{i+1:02}','stage-row-number'),False,False,4 if compact else 9)
            image=Gtk.Image();self.artwork.load(image,value.get('image',''),30 if compact else 42,6 if compact else 7);row.pack_start(image,False,False,0)
            names=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=1)
            play=button(value.get('title',''),lambda v=value:self.service.play_now(v,context=context),'stage-song')
            play.get_child().set_xalign(0);play.get_child().set_ellipsize(Pango.EllipsizeMode.END);play.get_child().set_max_width_chars(65)
            play.get_style_context().add_class('stage-card-title');names.pack_start(play,False,False,0)
            if compact:play.get_style_context().add_class('stage-song-compact')
            else:names.pack_start(label(value.get('artist',''),'stage-card-subtitle',65),False,False,5)
            row.pack_start(names,True,True,0);row.pack_start(label(duration(value),'stage-card-subtitle'),False,False,0)
            add=button('+',lambda v=value:self.add([v]),'stage-add',text('Add to queue: ','В очередь: ')+value.get('title',''))
            if compact:add.get_style_context().add_class('stage-add-compact')
            valid=bool(track(value,self.source));play.set_sensitive(valid);add.set_sensitive(valid)
            row.pack_end(add,False,False,0)
            (container if container is not None else self.content).pack_start(row,False,False,0);self.song_buttons.append((play,add,value))

    def resize(self,width,height):
        self.wide=width>=1200;self.height=height;self.crumb.set_visible(self.wide)
        size=(max(116,min(164,(width-160)//7-26)),88 if height<680 else 128 if height<800 else 164,self.wide,masthead_height(height))
        if self.size==size:return
        self.cancel_intro()
        self.size=size;self.card_size,self.portrait_size=size[:2]
        if self.active:self.render()

    def close(self):
        if self.overview_fit_idle:GLib.source_remove(self.overview_fit_idle);self.overview_fit_idle=0
        self.deactivate();self.closed=True;self.entrance.close();self.unsubscribe();self.cache.clear();self.banner_cache.clear()
