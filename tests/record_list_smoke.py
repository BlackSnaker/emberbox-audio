"""Offline list layout, current-record updates and independent row actions."""
import os,time
from functools import lru_cache
from pathlib import Path
from unittest.mock import patch
import fullscreen_smoke as f
import fullscreen
from gi.repository import Gdk,GdkPixbuf,Gtk
from source_picker import text


names=[('Afterglow','Mira Vale','Slow Evenings'),
       ('The City After Midnight','The Paper Satellites','Night Atlas'),
       ('Тихая сторона города','Северная комната','Между огнями'),
       ('Between Two Stations','Northbound & June Room','Paper Landscapes'),
       ('A Soft Place to Land (Piano Session)','Elin Grey','A Place to Stay'),
       ('A Long Way Home — Live at the Old Observatory (Expanded Evening Edition)','The Amber Archive & Mira Vale','Letters from the Observatory'),
       ('Amber Signals','June Room','Small Hours'),
       ('Paper Satellites','The Morning Assembly','In the Warm Light'),
       ('Музыка тёплого воздуха','Северная комната','Между огнями'),
       ('We Keep the Light On','Elin Grey & Northbound','A Place to Stay')]
items=[{'uri':f'apple:songs:{10000+i}','id':str(10000+i),'kind':'songs',
        'title':name+(f' · Session {i//len(names)+1}' if i>=len(names) else ''),
        'artist':artist,'album':album,'image':f'fixture:record:{i%len(names)}','duration_ms':(182+i%10*17)*1000}
       for i in range(80) for name,artist,album in [names[i%len(names)]]]


@lru_cache(maxsize=32)
def art(index,size):
    palettes=[('#394c52','#dba875'),('#233a4a','#9eae91'),('#574447','#dfaa7c'),
              ('#344844','#d9c78e'),('#4f5062','#dbb1a4'),('#574634','#e0be6d'),
              ('#374747','#b4b590'),('#535d42','#d1c099'),('#4f3e53','#cfa27b'),('#30464c','#b1c9b7')]
    dark,light=palettes[index%len(palettes)]
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128">
    <defs><linearGradient id="b" x2=".9" y2="1"><stop stop-color="{dark}"/><stop offset="1" stop-color="#18251e"/></linearGradient>
    <linearGradient id="l" x2="0" y2="1"><stop stop-color="{light}"/><stop offset="1" stop-color="{dark}"/></linearGradient></defs>
    <rect width="128" height="128" rx="20" fill="url(#b)"/>
    <circle cx="{47+index%3*12}" cy="43" r="23" fill="url(#l)"/>
    <path d="M0 92L38 60L70 88L104 49L128 75V109H0Z" fill="{light}" opacity=".30"/>
    <path d="M0 104L43 81L83 101L113 75L128 89V128H0Z" fill="#14261f" opacity=".65"/>
    <path d="M18 19H41M18 22H29" stroke="{light}" stroke-width="1" opacity=".65"/>
    <text x="16" y="113" fill="#f8e8bc" font-family="sans-serif" font-size="7" letter-spacing="1.1">EMBER SESSIONS</text></svg>'''
    loader=GdkPixbuf.PixbufLoader.new_with_type('svg');loader.set_size(size,size)
    loader.write(svg.encode());loader.close();return loader.get_pixbuf()


def load_art(_loader,image,url,size,radius=8,preserve=False,on_loaded=None,**options):
    index=int(url.rsplit(':',1)[-1]) if url.startswith('fixture:record:') else 0
    image.set_size_request(size,size);pixels=art(index,size);image.set_from_pixbuf(pixels)
    if on_loaded:on_loaded(pixels)


def settle(seconds=.1):
    until=time.monotonic()+seconds
    from gi.repository import GLib
    while time.monotonic()<until:
        for _ in range(6):
            if not GLib.MainContext.default().pending():break
            GLib.MainContext.default().iteration(False)
        time.sleep(.003)


def wait(predicate):
    until=time.monotonic()+3
    while not predicate() and time.monotonic()<until:settle(.03)
    assert predicate(),'The fixture playback request did not complete'


def shot(stage,name):
    folder=os.environ.get('EMBERBOX_RECORD_PREVIEW')
    if not folder:return
    target=Path(folder);target.mkdir(parents=True,exist_ok=True)
    stage.window.set_focus(None)
    settle(.2);width,height=stage.window.get_size()
    Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,width,height).savev(str(target/(name+'.png')),'png',[],[])


host=f.FixtureHost();host.source='apple-music'
host.apple_web.action=lambda *_a,**_kw:None
host.apple_web.state={'id':items[2]['id']}
host.title.set_text(items[2]['title']);host.artist.set_text(items[2]['artist'])
host.art_url=items[2]['image'];host.playing=True
plays=[];artists=[]
with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected network access')),\
     patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),patch.object(fullscreen.Artwork,'load',load_art):
    stage=fullscreen.FullscreenPlayer(host);host.fullscreen=stage
    stage.music.repository.play=lambda item,alive:plays.append(item['uri']) if alive() else None
    stage.music.repository.load=lambda *_a,**_kw:{'items':[]}
    try:
        stage.open();f.wait_transition(stage)
        stage.show_page('library');view=stage.library_view
        settle(.2)
        view.items=items;view.selected={'uri':'apple:library-playlists:fixture','kind':'library-playlists',
           'title':text('In the warm light','В тёплом свете'),'artist':'Ember Sessions','image':'fixture:record:5'}
        view.open_artist=lambda item:artists.append(item['uri'])
        view.render();settle(.3)
        table=view.track_table
        assert len(table.rows)==80
        assert table.rows[2].get_style_context().has_class('record-current')
        assert table.rows[2].rank.get_visible_child_name()=='current'
        assert all(not b.get_has_tooltip() for row in table.rows for b in row.action_buttons)
        assert not view.artist_button.get_visible(),'A multi-artist playlist must not expose a fake playlist artist'
        table.rows[0].action_buttons[0].clicked()
        assert not plays and len(stage.music.book.upcoming('apple-music'))==1
        table.rows[1].artist_button.clicked()
        assert artists==[items[1]['uri']] and not plays,'The artist link also started the song'
        table.rows[0].activate();wait(lambda:not stage.music.loading)
        assert plays==[items[0]['uri']],'Activating a row must dispatch exactly one play request'
        table.rows[4].grab_focus();settle(.03)
        original_calls=list(host.calls);volume=host.sound.volume
        f.key(stage.window,'space');wait(lambda:not stage.music.loading)
        assert plays==[items[0]['uri'],items[4]['uri']],'Keyboard row activation must play the chosen song'
        f.key(stage.window,'Down');f.key(stage.window,'Up')
        assert host.calls==original_calls and host.sound.volume==volume,'List navigation leaked into transport shortcuts'
        old_rows=tuple(table.rows)
        adjustment=view.scroll.get_vadjustment();adjustment.set_value(250);settle(.1)
        position=adjustment.get_value()
        host.apple_web.state['id']=items[3]['id'];host.title.set_text(items[3]['title']);host.artist.set_text(items[3]['artist'])
        host.length=items[3]['duration_ms']*1000;host.album.set_text(items[3]['album'])
        stage.update();settle(.1)
        assert view.track_table is table and tuple(table.rows)==old_rows,'Track updates rebuilt the list'
        assert abs(adjustment.get_value()-position)<1,'The list jumped while playback changed'
        assert table.rows[3].get_style_context().has_class('record-current')
        assert not table.rows[2].get_style_context().has_class('record-current')
        host.playing=False;view.update_playback()
        assert table.rows[3].indicator.get_icon_name()[0]=='media-playback-pause-symbolic'
        host.playing=True;view.update_playback()
        adjustment.set_value(0);table.rows[0].grab_focus();settle(.1)
        for width,height in ((1920,1080),(1280,720),(1024,600)):
            stage.window.unfullscreen();stage.window.resize(width,height);settle(.3)
            assert stage.window.get_size()==(width,height),'A long title widened the window'
            row=table.rows[0]
            assert row.album.get_visible()==(view.list_width>=1120)
            for widget in (row.play_button,row.artist_button,row.duration,row.action_buttons[0],view.entry):
                x,y=widget.translate_coordinates(stage.window,0,0);area=widget.get_allocation()
                assert x>=0 and x+area.width<=width,(width,type(widget).__name__,x,area.width)
            assert row.name.get_allocated_width()>width*.30,('Actions consumed the readable title column',width,row.name.get_allocated_width(),row.play_button.get_allocated_width(),row.get_allocated_width(),view.list_width)
            if height==600:assert view.scroll.get_allocated_height()>=155,'Compact navigation must leave room to read at least two records'
            if width==1920:
                assert row.album.get_allocated_width()>=200
                assert row.action_buttons[0].get_allocated_height()<=38,'The queue action stretched into a tall pill'
                shot(stage,'records-1920')
            elif width==1024:shot(stage,'records-1024')
        assert len(plays)==2 and len(artists)==1,'Layout and current-track updates must not change playback'
        print('PASS record list: 80 rows, responsive columns, independent row/artist/queue actions, keyboard navigation, current-song updates without rebuild or scroll jumps')
    finally:stage.close();host.window.destroy()
