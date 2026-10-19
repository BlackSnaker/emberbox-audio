"""An immersive Grunesphism listening room, separate from the desktop widget."""
import math
import time
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango
from artwork import Artwork
from cover_tint import cover_color, BASE_COLOR
from hardware_controls import MuteToggle, VolumeKnob
from nixie_spectrum import NixieSpectrum
from source_picker import SourcePicker, text
from lyrics import LyricsClient, active_line


CSS = b'''
window.ember-stage { background-color: #171b18; color: #ebdbb2; }
.ember-stage { font-family: 'Noto Sans'; }
.ember-stage button, .ember-stage button:focus { outline-style: none; outline-width: 0; }
.stage-brand { color: #fbf1c7; font-size: 17px; font-weight: bold; letter-spacing: 4px; }
.stage-overline { color: #a89984; font-size: 9px; letter-spacing: 2px; }
.stage-dot { color: #d79921; font-size: 10px; }
.ember-stage button.stage-quiet {
  background-color: rgba(255,241,206,0.025); background-image: none; min-height: 18px; min-width: 0;
  border: 1px solid rgba(255,241,206,0.045); border-radius: 18px;
  box-shadow: none; color: #bdae93; font-size: 11px; padding: 8px 13px;
}
.ember-stage button.stage-quiet:hover { background-color: rgba(255,241,206,0.055); color: #fbf1c7; }
.ember-stage button.stage-exit { border-radius: 16px; min-width: 21px; font-size: 17px; padding: 5px 10px; }
.stage-art-shell {
  padding: 9px; border-radius: 30px;
  background-color: rgba(17,21,17,0.6);
  box-shadow: 0 18px 48px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,241,206,0.08);
}
.stage-track-title { color: #fbf1c7; font-size: 34px; font-weight: bold; letter-spacing: -1px; }
.stage-artist { color: #bdae93; font-size: 17px; }
.stage-album { color: #928374; font-size: 11px; }
.stage-lyrics-heading { color: #bdae93; font-size: 10px; letter-spacing: 2px; }
.stage-lyric-scroll, .stage-lyric-scroll viewport { background-color: transparent; border: none; }
.stage-lyric-scroll scrollbar { background-color: transparent; }
.stage-lyric-scroll scrollbar slider { background-color: rgba(189,174,147,0.22); min-width: 3px; border-radius: 4px; }
.ember-stage button.stage-line {
  background-color: transparent; background-image: none; border: none; box-shadow: none;
  border-radius: 8px; padding: 14px 0; color: #6f7568;
  font-size: 30px; font-weight: bold; letter-spacing: -0.5px;
  transition-property: color; transition-duration: 420ms;
}
.ember-stage button.stage-line:hover { color: #bdae93; }
.ember-stage button.stage-line.stage-line-past { color: #929a83; }
.ember-stage button.stage-line.stage-line-active {
  color: #fff0c3; text-shadow: 0 0 20px rgba(250,189,47,0.16);
}
.stage-empty-title { color: #d5d4b8; font-size: 42px; font-weight: bold; letter-spacing: -1px; }
.stage-empty-note { color: #928374; font-size: 13px; }
.stage-provider { color: #928374; font-size: 10px; }
.ember-stage link { color: #a89984; }
.ember-stage button.stage-provider label { color: #a89984; }
.stage-console {
  border: 1px solid rgba(255,241,206,0.025); border-radius: 26px;
  background-image: linear-gradient(to bottom right, rgba(55,58,46,0.66), rgba(28,32,25,0.85));
  box-shadow: 0 10px 28px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,241,206,0.045);
  padding: 12px 22px;
}
.ember-stage button.stage-transport {
  color: #ebdbb2; font-size: 22px; padding: 12px; border: none; border-radius: 28px;
  min-width: 25px; min-height: 25px;
  background-image: linear-gradient(to bottom right, #363a2e, #24291f);
  box-shadow: -2px -2px 6px rgba(255,241,206,0.04), 4px 5px 9px rgba(0,0,0,0.24);
}
.ember-stage button.stage-transport:hover { color: #fabd2f; }
.ember-stage button.stage-play {
  background-image: linear-gradient(to bottom right, #ffda73, #e5aa2b); color: #282828;
  border-radius: 33px; min-width: 37px; min-height: 37px; font-size: 24px;
  box-shadow: -2px -2px 9px rgba(255,214,120,0.1), 4px 5px 12px rgba(0,0,0,0.25), inset 0 1px 0 #ffe9a3;
}
.ember-stage button.stage-play:hover { color: #282828; background-image: linear-gradient(to bottom right, #ffe299, #edb23b); }
.ember-stage button.stage-transport:active { box-shadow: inset 2px 3px 6px rgba(0,0,0,0.23); }
.ember-stage button.stage-transport:disabled { color: #646b59; }
.ember-stage scale { padding: 7px 0; }
.ember-stage scale trough { min-height: 4px; background-color: #151c16; border: none; border-radius: 4px; box-shadow: inset 0 1px 3px rgba(0,0,0,0.45); }
.ember-stage scale highlight { min-height: 4px; background-image: linear-gradient(to right, #b98231, #f2be57); border-radius: 4px; }
.ember-stage scale slider { background-image: none; background-color: #e8be69; border: none; box-shadow: none; min-width: 9px; min-height: 9px; }
.stage-time { color: #a89984; font-family: 'Noto Sans Mono'; font-size: 10px; }
.ember-stage button.hardware-toggle { background-image: none; background-color: transparent; border: none; box-shadow: none; padding: 0; }
.ember-stage .small-screen .stage-track-title { font-size: 25px; }
.ember-stage .small-screen button.stage-line { font-size: 24px; padding: 10px 0; }
.ember-stage .small-screen .stage-empty-title { font-size: 32px; }
.ember-stage .small-screen .stage-artist { font-size: 14px; }
'''


def clock_text(seconds):
    value=max(0,int(seconds))
    return f'{value//60}:{value%60:02d}'


def label(value, style, wrap=False):
    item=Gtk.Label(label=value)
    item.set_xalign(0)
    if style:item.get_style_context().add_class(style)
    item.set_line_wrap(wrap)
    item.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    return item


def background(width,height,color):
    # Simple vector gradients stay cheap and crisp; no per-frame image blur.
    accent=tuple(max(26,min(140,67+(value-base)*8)) for value,base in zip(color,BASE_COLOR))
    hue=f'rgb{accent}'
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 1600 1000" preserveAspectRatio="none">
    <defs><radialGradient id="a"><stop stop-color="{hue}" stop-opacity=".58"/><stop offset="1" stop-color="{hue}" stop-opacity="0"/></radialGradient>
    <radialGradient id="b"><stop stop-color="#9e7238" stop-opacity=".16"/><stop offset="1" stop-color="#9e7238" stop-opacity="0"/></radialGradient>
    <linearGradient id="v" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#0d1511" stop-opacity="0"/><stop offset="1" stop-color="#0c120e" stop-opacity=".65"/></linearGradient>
    <pattern id="p" width="6" height="6" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".45" fill="#f5eacb" opacity=".025"/></pattern></defs>
    <rect width="1600" height="1000" fill="#1b211b"/><ellipse cx="340" cy="350" rx="940" ry="780" fill="url(#a)"/>
    <ellipse cx="1480" cy="90" rx="680" ry="720" fill="url(#b)"/><rect width="1600" height="1000" fill="url(#v)"/>
    <rect width="1600" height="1000" fill="url(#p)"/></svg>'''
    loader=GdkPixbuf.PixbufLoader.new_with_type('svg')
    loader.write(svg.encode());loader.close()
    return loader.get_pixbuf()


class FullscreenPlayer:
    def __init__(self,host):
        self.host=host
        self.visible=False;self.closed=False;self.timer=0;self.tick=0
        self.track=None;self.art_key=None;self.art_size=380;self.palette=BASE_COLOR;self.bg_key=None;self.layout_size=None
        self.last_position=None;self.anchor=time.monotonic();self.position=0.
        self.levels=[0.]*9;self.velocities=[0.]*9;self.frame_time=None
        self.current_line=-2;self.line_buttons=[];self.line_labels=[];self.lyric_state=None
        self.scroll_target=None;self.manual_until=0.;self.pending_center=False;self.last_fade=0.
        self.artwork=Artwork()
        self.lyrics=LyricsClient(self.on_lyrics)
        self.window=Gtk.Window(title='Emberbox Audio · '+text('Listening room','Комната прослушивания'))
        self.window.set_name('emberbox-listening-room')
        self.window.get_style_context().add_class('ember-stage')
        self.window.set_decorated(False)
        self.window.set_default_size(1280,800)
        self.window.set_type_hint(Gdk.WindowTypeHint.NORMAL)
        self.window.connect('delete-event',lambda *_args:(self.hide(),True)[1])
        self.window.connect('key-press-event',self.on_key)
        provider=Gtk.CssProvider();provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(self.window.get_screen(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+5)
        self.provider=provider
        overlay=Gtk.Overlay();overlay.add(Gtk.Box());self.window.add(overlay)
        self.background=Gtk.Image();self.background.set_halign(Gtk.Align.FILL);self.background.set_valign(Gtk.Align.FILL)
        overlay.add_overlay(self.background);overlay.set_overlay_pass_through(self.background,True)
        self.layout=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=18)
        self.layout.set_halign(Gtk.Align.FILL);self.layout.set_valign(Gtk.Align.FILL)
        overlay.add_overlay(self.layout)
        header=Gtk.Box(spacing=12)
        wordmark=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3)
        wordmark.pack_start(label('EMBER','stage-brand'),False,False,0)
        wordmark.pack_start(label(text('THE LISTENING ROOM','КОМНАТА ПРОСЛУШИВАНИЯ'),'stage-overline'),False,False,0)
        header.pack_start(wordmark,True,True,0)
        self.source_button=self.button('',self.show_sources,'stage-quiet')
        header.pack_start(self.source_button,False,False,0)
        self.exit_button=self.button('↙',self.hide,'stage-quiet','stage-exit')
        self.source_button.set_valign(Gtk.Align.CENTER)
        self.exit_button.set_valign(Gtk.Align.CENTER)
        self.exit_button.get_accessible().set_name(text('Return to desktop · Esc','Вернуться на рабочий стол · Esc'))
        header.pack_end(self.exit_button,False,False,0)
        self.layout.pack_start(header,False,False,0)
        self.body=Gtk.Box(spacing=66)
        self.body.set_valign(Gtk.Align.CENTER)
        self.left=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        self.left.set_halign(Gtk.Align.START);self.left.set_valign(Gtk.Align.CENTER)
        art_shell=Gtk.Box();art_shell.get_style_context().add_class('stage-art-shell')
        art_shell.set_halign(Gtk.Align.START)
        self.cover=Gtk.Image();art_shell.pack_start(self.cover,False,False,0)
        self.left.pack_start(art_shell,False,False,0)
        self.title=label('','stage-track-title',True);self.title.set_lines(2);self.title.set_ellipsize(Pango.EllipsizeMode.END)
        self.left.pack_start(self.title,False,False,0)
        self.artist=label('','stage-artist');self.artist.set_ellipsize(Pango.EllipsizeMode.END)
        self.left.pack_start(self.artist,False,False,0)
        self.album=label('','stage-album');self.album.set_ellipsize(Pango.EllipsizeMode.END)
        self.left.pack_start(self.album,False,False,0)
        self.body.pack_start(self.left,False,False,0)
        right=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14)
        heading=Gtk.Box(spacing=10)
        self.lyric_heading=label(text('WORDS, IN YOUR RHYTHM','СТРОКИ В ТВОЁМ РИТМЕ'),'stage-lyrics-heading')
        heading.pack_start(self.lyric_heading,True,True,0)
        self.follow=self.button(text('Follow','Следовать'),self.follow_lyrics,'stage-quiet')
        heading.pack_end(self.follow,False,False,0)
        right.pack_start(heading,False,False,0)
        self.lyric_stack=Gtk.Stack();self.lyric_stack.set_hhomogeneous(False);self.lyric_stack.set_vhomogeneous(False);self.lyric_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.lyric_stack.set_transition_duration(450)
        self.lyrics_scroll=Gtk.ScrolledWindow();self.lyrics_scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        self.lyrics_scroll.get_style_context().add_class('stage-lyric-scroll')
        self.lyrics_scroll.set_overlay_scrolling(True)
        self.lyrics_scroll.connect('scroll-event',self.on_manual_scroll)
        self.lines_box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3)
        self.lines_box.set_margin_top(50);self.lines_box.set_margin_bottom(80)
        self.lyrics_scroll.add(self.lines_box)
        self.lyric_stack.add_named(self.lyrics_scroll,'lines')
        empty=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=20)
        empty.set_valign(Gtk.Align.CENTER)
        empty.pack_start(label('∿','stage-empty-title'),False,False,0)
        self.empty_title=label('','stage-empty-title',True);empty.pack_start(self.empty_title,False,False,0)
        self.empty_note=label('','stage-empty-note',True);empty.pack_start(self.empty_note,False,False,0)
        self.retry_button=self.button(text('Try again','Попробовать ещё'),self.retry_lyrics,'stage-quiet')
        self.retry_button.set_halign(Gtk.Align.START);empty.pack_start(self.retry_button,False,False,0)
        self.lyric_stack.add_named(empty,'empty')
        right.pack_start(self.lyric_stack,True,True,0)
        foot=Gtk.Box(spacing=10)
        self.lyric_note=label('','stage-provider');foot.pack_start(self.lyric_note,True,True,0)
        self.credit=Gtk.LinkButton.new_with_label('https://lrclib.net/','LRCLIB ↗')
        self.credit.set_has_tooltip(False);self.credit.get_style_context().add_class('stage-provider')
        foot.pack_end(self.credit,False,False,0);right.pack_start(foot,False,False,0)
        self.body.pack_start(right,True,True,0)
        self.layout.pack_start(self.body,True,True,0)
        footer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        progress=Gtk.Box(spacing=14)
        self.elapsed=label('0:00','stage-time');progress.pack_start(self.elapsed,False,False,0)
        self.progress=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,0,1,.1)
        self.progress.set_draw_value(False);self.progress.set_hexpand(True)
        self.progress.connect('change-value',self.on_seek);progress.pack_start(self.progress,True,True,0)
        self.total=label('0:00','stage-time');progress.pack_end(self.total,False,False,0)
        footer.pack_start(progress,False,False,0)
        console=Gtk.Box(spacing=28);console.get_style_context().add_class('stage-console')
        spectrum_box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=2)
        spectrum_box.set_hexpand(True);spectrum_box.set_halign(Gtk.Align.START)
        self.equalizer=NixieSpectrum();self.equalizer.set_compact(True)
        spectrum_box.pack_start(self.equalizer,False,False,0)
        caption=label(text('●  LIVE SOUND','●  ЖИВОЙ ЗВУК'),'stage-overline');caption.set_halign(Gtk.Align.CENTER)
        spectrum_box.pack_start(caption,False,False,0)
        console.pack_start(spectrum_box,True,True,0)
        transport=Gtk.Box(spacing=17);transport.set_valign(Gtk.Align.CENTER)
        self.previous_button=self.button('⏮',lambda:self.action('previous'),'stage-transport')
        self.play_button=self.button('Ⅱ',lambda:self.action('toggle'),'stage-transport','stage-play')
        self.next_button=self.button('⏭',lambda:self.action('next'),'stage-transport')
        for b in (self.previous_button,self.play_button,self.next_button):transport.pack_start(b,False,False,0)
        console.pack_start(transport,False,False,0)
        volume_box=Gtk.Box(spacing=8);volume_box.set_hexpand(True);volume_box.set_halign(Gtk.Align.END)
        volume_box.set_valign(Gtk.Align.CENTER)
        self.mute=MuteToggle(host.sound.toggle_mute);self.mute.set_compact(True)
        volume_box.pack_start(self.mute,False,False,0)
        self.volume=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,0,1,.01)
        self.volume.set_draw_value(False);self.volume.set_size_request(85,-1)
        self.volume.connect('change-value',self.on_volume);volume_box.pack_start(self.volume,False,False,0)
        self.knob=VolumeKnob(host.sound.set_volume)
        volume_box.pack_start(self.knob,False,False,0)
        console.pack_end(volume_box,True,True,0)
        footer.pack_start(console,False,False,0)
        self.layout.pack_end(footer,False,False,0)
        self.source_picker=SourcePicker(lambda source,session=None:host.select_source(source,session),lambda:None,self.open_accounts)
        self.layout.show_all()
        self.follow.hide();self.retry_button.hide()

    def button(self,value,callback,*styles):
        b=Gtk.Button(label=value)
        for style in styles:b.get_style_context().add_class(style)
        b.set_has_tooltip(False)
        b.connect('clicked',lambda _b:callback())
        return b

    def open(self):
        if self.closed:return
        if self.visible:
            self.window.present()
            return
        self.visible=True
        self.current_line=-2;self.last_position=None;self.frame_time=None;self.manual_until=0.
        display=self.host.window.get_display()
        native=self.host.window.get_window()
        monitor=display.get_monitor_at_window(native) if native else display.get_primary_monitor()
        if monitor:
            index=next((i for i in range(display.get_n_monitors()) if display.get_monitor(i)==monitor),0)
            self.window.fullscreen_on_monitor(self.window.get_screen(),index)
        else:self.window.fullscreen()
        self.window.show_all()
        self.retry_button.hide();self.follow.hide()
        self.window.present()
        self.update()
        if not self.timer:self.timer=GLib.timeout_add(100,self.update)
        if not self.tick:self.tick=self.window.add_tick_callback(self.animate)

    def hide(self):
        self.visible=False
        self.track=None
        self.lyrics.set_track('','')
        self.window.unfullscreen();self.window.hide()
        if self.timer:GLib.source_remove(self.timer);self.timer=0
        if self.tick:self.window.remove_tick_callback(self.tick);self.tick=0
        self.frame_time=None
        if self.source_picker.popover:self.source_picker.popover.popdown()

    def close(self):
        if self.closed:return
        self.hide();self.closed=True
        self.lyrics.close()
        self.artwork.pool.shutdown(wait=False,cancel_futures=True)
        Gtk.StyleContext.remove_provider_for_screen(self.window.get_screen(),self.provider)
        self.window.destroy()

    def on_size(self,_window,allocation):
        width,height=allocation.width,allocation.height
        if width<100 or height<100 or self.layout_size==(width,height):return
        self.layout_size=(width,height)
        small=height<850 or width<1200
        self.equalizer.set_compact(small)
        context=self.layout.get_style_context()
        context.add_class('small-screen') if small else context.remove_class('small-screen')
        margin=max(24,min(88,int(width*.047)))
        self.layout.set_margin_start(margin);self.layout.set_margin_end(margin)
        self.layout.set_margin_top(24 if small else 36);self.layout.set_margin_bottom(22 if small else 32)
        self.body.set_spacing(max(32,min(100,int(width*.052))))
        size=max(180,min(560,int(width*.34),height-(410 if small else 460)))
        if size!=self.art_size:
            self.art_size=size
            self.left.set_size_request(size+18,-1)
            self.title.set_max_width_chars(max(10,int(size/17)))
            self.load_art()
        self.paint_background(width,height)
        if self.current_line>=0:self.pending_center=True
        self.layout.queue_resize()
        self.window.queue_resize()

    def paint_background(self,width=None,height=None):
        if width is None:width,height=self.window.get_size()
        key=(width,height,self.palette)
        if key==self.bg_key:return
        self.bg_key=key
        self.background.set_from_pixbuf(background(max(1,width),max(1,height),self.palette))

    def load_art(self):
        url=self.host.art_url or ''
        key=(url,self.art_size)
        if key==self.art_key:return
        self.art_key=key
        self.artwork.load(self.cover,url,self.art_size,22,preserve=True,on_loaded=self.on_art)

    def on_art(self,pixbuf):
        if self.closed:return
        self.palette=cover_color(pixbuf)
        self.paint_background()

    def show_sources(self):
        h=self.host
        self.source_picker.show(self.source_button,h.source,h.sessions,h.browser_binding,h.youtube_binding,h.youtube_mode)

    def open_accounts(self):
        self.hide();self.host.show_accounts()

    def action(self,action):
        self.host.on_action(None,action)
        self.update()

    def on_seek(self,_scale,_scroll,value):
        if self.host.progress_event.get_sensitive():self.host.seek_to(value)
        return True

    def on_volume(self,_scale,_scroll,value):
        if self.host.sound.available:self.host.sound.set_volume(value)
        return True

    def on_key(self,_window,event):
        key=Gdk.keyval_name(event.keyval)
        if key in ('Escape','F11'):self.hide();return True
        if key in ('space','XF86AudioPlay'):self.action('toggle');return True
        if key in ('Left','Right'):
            if self.host.progress_event.get_sensitive() and self.host.length>0:
                self.host.seek_to(max(0,min(self.host.length/1e6,self.position+(-10 if key=='Left' else 10))))
            return True
        if key in ('Up','Down'):
            if self.host.sound.available:self.host.sound.set_volume(max(0,min(1,self.host.sound.volume+(.03 if key=='Up' else -.03))))
            return True
        return False

    def update(self):
        if not self.visible or self.closed:return False
        h=self.host
        width,height=self.window.get_size()
        if self.layout_size!=(width,height):
            from types import SimpleNamespace
            self.on_size(self.window,SimpleNamespace(width=width,height=height))
        title,artist,album=h.title.get_text(),h.artist.get_text(),h.album.get_text()
        for item,value in ((self.title,title),(self.artist,artist),(self.album,album)):
            if item.get_text()!=value:item.set_text(value)
        names={'spotify':'Spotify','apple-music':'Apple Music','youtube':'YouTube','yandex-music':text('Yandex Music','Яндекс Музыка')}
        for button,value in ((self.source_button,'●  '+names.get(h.source,h.source)+'  ⌄'),(self.play_button,'Ⅱ' if h.playing else '▶')):
            if button.get_label()!=value:
                button.set_label(value)
                button.get_child().show()
        self.play_button.set_sensitive(h.play.get_sensitive())
        self.previous_button.set_sensitive(h.previous.get_sensitive());self.next_button.set_sensitive(h.next.get_sensitive())
        seconds=max(0,h.position/1e6)
        if self.last_position!=h.position or not h.playing:
            self.last_position=h.position;self.anchor=time.monotonic()
        self.position=min(h.length/1e6 if h.length else seconds,seconds+min(1.8,time.monotonic()-self.anchor) if h.playing else seconds)
        self.progress.set_range(0,max(1,h.length/1e6));self.progress.set_value(self.position)
        self.progress.set_sensitive(h.progress_event.get_sensitive() and h.length>0)
        self.elapsed.set_text(clock_text(self.position));self.total.set_text(clock_text(h.length/1e6))
        self.volume.set_value(0 if h.sound.muted else h.sound.volume);self.volume.set_sensitive(h.sound.available)
        self.mute.set_state(h.sound.volume,h.sound.muted,h.sound.available)
        self.knob.set_state(h.sound.volume,h.sound.muted,h.sound.available)
        self.load_art()
        identity=(h.source,title,artist,album,round(h.length/1e6))
        if identity!=self.track:
            self.track=identity;self.current_line=-2;self.manual_until=0.;self.last_position=None
            # No network activity for the desktop widget or empty player states.
            valid=bool(h.length>0 and title and artist)
            self.lyrics.set_track(title if valid else '',artist if valid else '',album if valid else '',h.length/1e6)
        self.update_line()
        return True

    def on_lyrics(self):
        if self.closed or not self.visible:return
        state=self.lyrics.state
        self.lyric_state=state;self.current_line=-2;self.scroll_target=None
        for child in self.lines_box.get_children():child.destroy()
        self.line_buttons=[];self.line_labels=[]
        if state.status=='ready' and (state.lines or state.plain):
            entries=[line.text for line in state.lines] if state.synced else state.plain.splitlines()
            for index,value in enumerate(entries[:600]):
                line=label(value or '♪','',True);line.set_hexpand(True)
                b=self.button('',lambda i=index:self.seek_line(i),'stage-line')
                b.remove(b.get_child());b.add(line)
                b.set_halign(Gtk.Align.FILL);line.set_halign(Gtk.Align.FILL)
                self.lines_box.pack_start(b,False,False,0)
                self.line_buttons.append(b);self.line_labels.append(line)
            self.lines_box.show_all()
            self.lyric_stack.set_visible_child_name('lines')
            self.lyric_note.set_text(text('Tap a line to go there','Нажми на строку, чтобы перемотать') if state.synced else text('Text without timecodes','Текст без таймкодов'))
            self.credit.show()
            self.follow.set_visible(state.synced)
            GLib.idle_add(self.update_line,True,priority=GLib.PRIORITY_DEFAULT)
        else:
            values={
                'loading':(text('A moment\nfor the words.','Сейчас найдём\nнужные слова.'),text('Your music keeps playing.','Музыка продолжает звучать.')),
                'instrumental':(text('Let the sound\nspeak.','Пусть говорит\nмузыка.'),text('An instrumental. Just you and the sound.','Инструментальная композиция. Только ты и звук.')),
                'missing':(text('Only the music.\nAnd you.','Только музыка.\nИ ты.'),text('No lyrics found for this recording yet.','Для этой записи текст пока не найден.')),
                'error':(text('Stay in\nthe moment.','Останься\nв моменте.'),text('Lyrics are unavailable right now.','Слова сейчас недоступны.')),
                'idle':(text('Make room\nfor the music.','Время\nдля музыки.'),text('Play a song to begin.','Включи песню, чтобы начать.'))}
            title,note=values.get(state.status,values['idle'])
            self.empty_title.set_text(title);self.empty_note.set_text(note)
            self.lyric_stack.set_visible_child_name('empty');self.follow.hide();self.credit.hide()
            self.retry_button.set_visible(state.status=='error')
            self.lyric_note.set_text('')
        self.update_line(True)

    def update_line(self,force=False):
        state=self.lyrics.state
        if not state.synced or not state.lines:return False
        index=active_line(state.lines,self.position)
        if not force and index==self.current_line:return False
        self.current_line=index
        for i,b in enumerate(self.line_buttons):
            style=b.get_style_context()
            style.remove_class('stage-line-active');style.remove_class('stage-line-past')
            if i==index and state.lines[i].text.strip():style.add_class('stage-line-active')
            elif i<index:style.add_class('stage-line-past')
        self.pending_center=True
        GLib.idle_add(self.center_line,priority=GLib.PRIORITY_DEFAULT)
        return False

    def center_line(self):
        if not self.visible or time.monotonic()<self.manual_until:return False
        if 0<=self.current_line<len(self.line_buttons):
            b=self.line_buttons[self.current_line]
            if b.get_allocated_height()<=1:return False
            point=b.translate_coordinates(self.lines_box,0,0)
            adjustment=self.lyrics_scroll.get_vadjustment()
            self.pending_center=False
            if point:self.scroll_target=max(0,min(adjustment.get_upper()-adjustment.get_page_size(),point[1]+b.get_allocated_height()/2-adjustment.get_page_size()/2))
        return False

    def on_manual_scroll(self,*_args):
        self.manual_until=time.monotonic()+7;self.scroll_target=None
        return False

    def follow_lyrics(self):
        self.manual_until=0.;self.center_line()

    def seek_line(self,index):
        state=self.lyrics.state
        if state.synced and index<len(state.lines) and self.host.progress_event.get_sensitive():
            self.host.seek_to(state.lines[index].seconds)
            self.manual_until=0.

    def retry_lyrics(self):
        h=self.host
        self.lyrics.set_track(h.title.get_text(),h.artist.get_text(),h.album.get_text(),h.length/1e6,force=True)

    def fade_lines(self):
        height=self.lyrics_scroll.get_allocated_height()
        if height<80:return
        for b in self.line_buttons:
            if b.get_allocated_height()<=1:continue
            point=b.translate_coordinates(self.lyrics_scroll,0,0)
            if point is None:continue
            center=point[1]+b.get_allocated_height()/2
            opacity=max(0.,min(1.,center/44,(height-center)/44))
            if abs(b.get_opacity()-opacity)>.015:b.set_opacity(opacity)

    def animate(self,_window,clock):
        now=clock.get_frame_time()
        dt=min(.05,(now-self.frame_time)/1e6) if self.frame_time else 1/60
        self.frame_time=now
        if self.pending_center:self.center_line()
        if time.monotonic()-self.last_fade>.1:
            self.last_fade=time.monotonic();self.fade_lines()
        meter=self.host.meter
        targets=meter.levels if self.host.playing and time.monotonic()-meter.last_sample<.35 else (0.,)*9
        for i,(old,target) in enumerate(zip(self.levels,targets)):
            rate=24. if target>old else 11.
            offset=old-target;momentum=self.velocities[i]+rate*offset;decay=math.exp(-rate*dt)
            self.levels[i]=max(0,min(1,target+(offset+momentum*dt)*decay))
            self.velocities[i]=(self.velocities[i]-rate*momentum*dt)*decay
        self.equalizer.set_levels(self.levels)
        if self.scroll_target is not None and time.monotonic()>=self.manual_until:
            adjustment=self.lyrics_scroll.get_vadjustment();current=adjustment.get_value()
            difference=self.scroll_target-current
            adjustment.set_value(self.scroll_target if abs(difference)<.5 else current+difference*(1-math.exp(-dt*7)))
            if abs(difference)<.5:self.scroll_target=None
        return True
