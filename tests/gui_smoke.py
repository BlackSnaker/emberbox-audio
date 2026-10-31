"""Offline GTK regression checks; never connect to the real player or audio."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
fixture=tempfile.TemporaryDirectory(prefix='emberbox-gui-')
os.environ['XDG_CONFIG_HOME']=str(Path(fixture.name)/'config')
os.environ['XDG_CACHE_HOME']=str(Path(fixture.name)/'cache')
os.environ['XDG_RUNTIME_DIR'] = str(Path(fixture.name) / 'runtime')
Path(os.environ['XDG_RUNTIME_DIR']).mkdir(mode=0o700)
sys.path.insert(0,str(ROOT/'src'))
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib
import widget


def settle(seconds=.3):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.01)

class DummySound:
    def __init__(self,changed):
        self.volume=.6;self.muted=False;self.available=False;self.changed=changed
    def refresh(self,_player):self.target=_player
    def set_volume(self,_value):pass
    def toggle_mute(self):pass
    def close(self):pass
    def flush(self):self.flushed=True
widget.SpotifyVolume=DummySound
def image_load(self,image,url,size,radius=8,preserve=False,on_loaded=None,**options):
    image.set_size_request(size,size)
    current=image.get_pixbuf()
    if current:
        from gi.repository import GdkPixbuf
        image.set_from_pixbuf(current.scale_simple(size,size,GdkPixbuf.InterpType.BILINEAR))
widget.Artwork.load=image_load
from sources import Session
class DummyMonitor:
    def __init__(self, connection, changed): self.changed=changed;self.calls=[]
    def poll(self): pass
    def call(self, session, method, args=None, root=False): self.calls.append((session.name,method))
    def close(self): pass
widget.Monitor=DummyMonitor
widget.SpotifyAudioMeter.start=lambda self:None
class DummyAppleWeb:
    native=True
    def __init__(self,changed):
        self.state={};self.enabled=False;self.connected=True;self.pid=12345;self.error='';self.calls=[]
    def set_enabled(self,value):self.enabled=value
    def ensure_started(self):pass
    def poll(self):pass
    def action(self,method,**params):self.calls.append((method,params))
    def request(self,method,**params):
        self.calls.append((method,params));return {'items':[],'tracks':[],'next':None}
    def close(self):pass
widget.AppleWeb=DummyAppleWeb
widget.YandexWeb=DummyAppleWeb
widget.SpotifyWeb=DummyAppleWeb
app=widget.Widget()
try:
    settle()
    assert app.window.get_size().width==460
    assert app.hide_button.get_visible() and app.close_button.get_visible()
    before=app.youtube.paused
    app.hide_button.clicked();settle()
    assert not app.window.get_visible() and app.youtube.paused==before
    app.show_widget();settle()
    assert app.window.get_visible() and app.window.get_size().width==460
    assert app.settings_button.get_visible()
    app.settings_button.clicked()
    settle()
    assert app.settings.popover.get_visible()
    assert app.settings.hide_button.get_visible() and app.settings.quit_button.get_visible()
    app.settings.mode_button.clicked()
    settle(.6)
    assert app.compact and app.compact_settings.get_visible()
    assert app.window.get_size().width==320
    app.compact_settings.clicked()
    settle()
    assert app.settings.popover.get_visible()
    app.settings.mode_button.clicked()
    settle(.6)
    assert not app.compact
    app.toggle_compact(None)
    settle(.6)
    assert app.window.get_size().width==320
    assert not app.title.get_visible()
    app.toggle_compact(None)
    settle(.6)
    assert app.window.get_size().width==460
    app.toggle_compact(None);settle(.08)
    assert app.layout_transition.active and not app.layout_transition.root.get_mapped()
    app.toggle_compact(None);settle(.6)
    assert not app.compact and not app.layout_transition.active
    assert app.layout_transition.root.get_mapped() and not app.layout_transition.frames
    app.toggle_compact(None);settle(.08)
    app.hide_widget()
    assert not app.layout_transition.active and not app.layout_transition.frames
    app.show_widget();app.toggle_compact(None);settle(.6)
    assert not app.compact and app.window.get_size().width==460
    app.show_accounts()
    assert app.library_stack.get_visible_child() is app.account_panel
    app.accounts.spotify=['fixture-spotify'];app.accounts.spotify_checked=True
    with patch.object(app.accounts,'open_spotify') as open_spotify, patch('accounts.launch') as external:
        app.accounts.connect('spotify')
        open_spotify.assert_not_called()
        assert app.spotify_web.calls[-1]==('show',{})
        assert 'desktop client' in app.accounts.state('spotify')['description']
        external.assert_not_called()
    before=app.source
    app.accounts.connect('apple-music')
    assert app.apple_web.calls[-1]==('show',{})
    app.apple_web.state={'ready':True,'authorized':True}
    app.on_apple_changed()
    assert app.apple_web.calls[-1]==('hide',{}) and not app.accounts.pending['apple-music']
    assert app.source==before  # Signing in never pauses or switches playback.
    app.account_panel.update()
    assert app.account_panel.cards['apple-music']['listen'].get_visible()
    app.account_panel.cards['apple-music']['listen'].clicked()
    assert app.apple_native() and not app.accounts_visible
    spotify=Session('org.mpris.MediaPlayer2.spotify', 'Spotify', 'spotify', 1,
        {'PlaybackStatus':'Playing','CanSeek':True,'Metadata':{'xesam:title':'Spotify track',
        'mpris:trackid':'/org/fixture/spotify','mpris:length':200000000}})
    browser=Session('org.mpris.MediaPlayer2.firefox.instance123', 'Firefox', 'firefox', 2,
        {'PlaybackStatus':'Paused','Metadata':{'xesam:title':'Apple track'}})
    app.select_source('spotify',spotify)
    app.on_sessions([spotify,browser])
    assert app.title.get_text()=='Spotify track'
    assert not app.album_button.get_sensitive()
    spotify.properties['Metadata']['xesam:album']='Original album'
    app.on_sessions([spotify,browser]);assert app.album_button.get_sensitive()
    # The desktop and Mini cover must follow confirmed playback without any
    # extra transport command or shift of neighbouring controls.
    from gi.repository import GdkPixbuf
    art=GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,True,8,112,112);art.fill(0x71875aff)
    spotify.properties['Metadata']['mpris:artUrl']='fixture:pause-cover'
    app.on_sessions([spotify,browser]);app.cover.set_from_pixbuf(art);app.sync_cover_pause()
    settle(.2)
    original_size=tuple(app.window.get_size());original_calls=list(app.monitor.calls)
    spotify.properties['PlaybackStatus']='Paused';app.on_sessions([spotify,browser]);settle(.2)
    assert app.cover_pause.tick and app.cover_pause.target==1 and 0<app.cover_pause.depth<1
    assert tuple(app.window.get_size())==original_size,(original_size,tuple(app.window.get_size()))
    app.toggle_compact(None);settle(.6)
    assert app.cover_pause.size==64 and app.cover_pause.depth==1 and not app.cover_pause.tick
    app.toggle_compact(None);settle(.6)
    assert app.cover_pause.size==112 and app.cover_pause.depth==1
    spotify.properties['PlaybackStatus']='Playing';app.on_sessions([spotify,browser]);settle(.1)
    assert app.cover_pause.target==0 and app.cover_pause.tick
    assert app.monitor.calls==original_calls,'Cover animation must not dispatch playback commands'
    assert not app.album_button.get_has_tooltip()
    transport_count=len(app.monitor.calls)
    with patch.object(widget.FullscreenPlayer,'open_album') as album:
        app.album_button.clicked();album.assert_called_once()
    assert len(app.monitor.calls)==transport_count,'The widget album link must not start or pause music'
    app.seek_to(17)
    assert app.monitor.calls[-1]==(spotify.name,'SetPosition')
    spotify.properties['CanSeek']=False
    count=len(app.monitor.calls);app.seek_to(22)
    assert len(app.monitor.calls)==count
    spotify.properties['CanSeek']=True
    with patch.object(app.music.repository,'play') as queued_play:
        app.music.play_all([{'uri':'spotify:track:QUEUEA','title':'Queue A'},
                            {'uri':'spotify:track:QUEUEB','title':'Queue B'}])
        settle(.15)
        transport_count=len(app.monitor.calls)
        app.on_action(None,'next');settle(.15)
        assert [call.args[0]['id'] for call in queued_play.call_args_list]==['QUEUEA','QUEUEB']
        assert len(app.monitor.calls)==transport_count,'Managed Next must use the custom queue'
        app.music.stop()
    with patch('widget.launch_desktop') as launch:
        app.open_spotify_login()
        assert app.monitor.calls[-1]==(spotify.name,'Raise')
        launch.assert_not_called()
    app.monitor.calls.clear()
    app.select_source('apple-music',browser)
    assert app.title.get_text()=='Apple track'
    assert app.monitor.calls==[(spotify.name,'Pause')]
    app.on_action(None,'next')
    assert app.monitor.calls[-1]==(browser.name,'Next')
    app.toggle_compact(None)
    settle(.6)
    assert app.window.get_size().width==320
    assert app.compact_source.get_visible()
    app.show_sources(app.compact_source)
    settle()
    assert app.source_picker.popover.get_visible()
    app.source_picker.popover.popdown()
    app.toggle_compact(None)
    settle(.6)
    app.select_source('spotify',spotify)
    assert app.title.get_text()=='Spotify track'
    assert not app.source_picker.popover.get_visible()
    app.expanded=True;app.apply_layout()
    app.select_source('apple-music',browser)
    assert app.drawer.get_reveal_child()
    assert app.library_stack.get_visible_child() is app.apple_panel
    assert 'library' in app.discovery_name.get_text().lower()
    app.select_source('spotify')
    assert app.drawer.get_reveal_child()
    panel=app.panel
    panel.data={'shelves':[{'title':'Evening','items':[]},{'title':'Morning','items':[]}]}
    panel.render_filters()
    chips=panel.filters.get_children()
    panel.select_shelf(chips[1],1)
    assert panel._active_shelf==1
    assert chips[1].get_active() and not chips[0].get_active()
    panel.select_shelf(chips[0],0)
    assert panel._active_shelf==0
    assert chips[0].get_active() and not chips[1].get_active()
    app.select_source('youtube')
    settle()
    assert app.youtube_native() and app.expanded and not app.compact
    assert app.library_stack.get_visible_child() is app.youtube_panel
    first={'id':'jNQXAC9IVRw','url':'https://www.youtube.com/watch?v=jNQXAC9IVRw',
           'title':'YouTube fixture','channel':'Fixture','duration':19}
    with patch.object(app.youtube,'_ensure_player',return_value=False), patch('widget.launch_desktop') as launch:
        app.youtube_panel.on_results([first],None)
        app.youtube_panel.buttons[0][0].clicked()
        assert app.youtube.current['id']==first['id']
        assert app.title.get_text()=='YouTube fixture'
        launch.assert_not_called()
        app.youtube_panel.entry.set_text('https://youtu.be/jNQXAC9IVRw?t=4')
        app.youtube_panel.submit()
        assert app.youtube.position==4
        launch.assert_not_called()
    app.toggle_compact(None)
    settle(.6)
    assert app.window.get_size().width==320 and app.compact_source.get_label()=='Y⌄'
    app.select_source('spotify')
    assert not app.youtube.enabled and app.youtube.paused
    app.select_source('apple-music')
    settle()
    assert app.apple_native() and app.apple_web.enabled
    assert app.apple_panel.bridge is app.apple_web and app.apple_panel.native
    assert app.library_stack.get_visible_child() is app.apple_panel and app.expanded
    app.apple_web.state={'ready':True,'authorized':True,'title':'Apple fixture','artist':'Fixture artist',
                         'duration':200,'position':20,'playing':True,'canNext':True,'canPrevious':True,
                         'audioQuality':{'codec':'aac','sampleRate':44100,'channels':2,'evidence':'decoder'},
                         'availableFormats':['dolby-atmos','lossless']}
    app.render_apple()
    assert app.title.get_text()=='Apple fixture' and app.playing
    assert app.sound.target.pid==12345 and app.sound.target.source=='apple-music'
    assert app.sound.target.family==''
    settle(.6)  # The source change may still be revealing the full widget.
    assert app.quality.get_mapped() and 'AAC' in app.quality.get_label()
    assert not app.quality.get_has_tooltip()
    app.quality.clicked();settle(.15)
    assert app.quality.popover.get_visible()
    assert app.quality.model['available']==['Dolby Atmos','Lossless']
    assert 'Atmos' not in app.quality.get_label()
    app.quality.popover.popdown()
    # Natural track changes briefly report empty/paused metadata. Cached cover
    # replacement, tint transitions and spectrum updates must keep painting.
    paints=app.frame_health.paints
    cover=widget.GdkPixbuf.Pixbuf.new(widget.GdkPixbuf.Colorspace.RGB,False,8,24,24)
    for index in range(3):
        app.apple_web.state={'ready':True,'authorized':True,'playing':False}
        app.render_apple();settle()
        app.apple_web.state={'ready':True,'authorized':True,'playing':True,
            'title':f'Next fixture {index}','duration':180,'position':1,
            'image':f'fixture:{index}','canNext':True,'canPrevious':True}
        app.render_apple()
        cover.fill((0xd79921ff,0x83a598ff,0xb16286ff)[index])
        app.on_cover_loaded(cover)
        settle()
        assert app.title.get_text()==f'Next fixture {index}' and app.playing
        assert app.frame_health.paints>paints
        paints=app.frame_health.paints
    # A lost frame callback is repaired by a GLib timer, while fully obscured
    # desktop windows are left asleep. This works without pycairo installed.
    app.window.remove_tick_callback(app.frame_health.tick)
    app.frame_health.tick=0
    app.frame_health.last_frame=time.monotonic()-3
    app.frame_health.obscured=True
    recovered=app.frame_health.recoveries
    app.frame_health.check()
    assert app.frame_health.recoveries==recovered
    app.frame_health.obscured=False
    app.frame_health.check()
    settle()
    assert app.frame_health.recoveries>=recovered+1
    assert app.frame_health.paints>paints
    assert time.monotonic()-app.frame_health.last_frame<.3
    with patch('widget.launch_desktop') as launch:
        app.on_action(None,'toggle');app.on_action(None,'next')
        assert app.apple_web.calls[-2:]==[('transport',{'action':'toggle'}),('transport',{'action':'next'})]
        app.apple_panel.category='songs'
        song={'id':'i.fixture','kind':'library-songs','title':'Fixture song','artist':'Artist',
              'duration_ms':200000,'uri':'apple:library-songs:i.fixture','image':''}
        app.apple_panel.pages={'songs':{'items':[song],'next':None}}
        app.apple_panel.render_page()
        app.apple_panel.track_buttons[0][0].clicked()
        settle()
        assert ('play',{'kind':'library-songs','id':'i.fixture'}) in app.apple_web.calls
        launch.assert_not_called()
    app.toggle_compact(None);settle(.6)
    assert app.window.get_size().width==320 and app.compact_source.get_label()=='A⌄'
    app.select_source('spotify')
    assert not app.apple_web.enabled
    app.accounts.connect('yandex-music')
    assert app.yandex_web.calls[-1]==('show',{})
    assert app.source=='spotify'
    app.yandex_web.state={'ready':True,'authorized':True,'subscribed':True,'title':'Wave fixture',
        'artist':'Fixture artist','duration':180,'position':2,'playing':True,'canNext':True,'wave':True}
    app.on_yandex_changed()
    assert app.yandex_web.calls[-1]==('hide',{})
    app.select_source('yandex-music');settle()
    assert app.native_web() is app.yandex_web and app.yandex_web.enabled
    assert not app.apple_web.enabled and not app.youtube.enabled
    assert app.title.get_text()=='Wave fixture' and app.playing
    assert app.sound.target.source=='yandex-music' and app.sound.target.pid==12345
    app.on_action(None,'next');app.seek_to(42)
    assert app.yandex_web.calls[-2:]==[('transport',{'action':'next'}),('seek',{'position':42})]
    app.show_yandex();settle()
    assert app.library_stack.get_visible_child() is app.yandex_panel
    app.yandex_panel.wave_button.clicked();settle()
    assert ('wave',{}) in app.yandex_web.calls
    app.yandex_panel.entry.set_text('Fixture');app.yandex_panel.search();settle()
    assert ('search',{'term':'Fixture'}) in app.yandex_web.calls
    result={'id':'123','uri':'yandex:track:123','title':'Fixture','artist':'Artist','image':''}
    app.yandex_panel.render([result,dict(result,id='456',uri='yandex:track:456',title='Next fixture')])
    original_request=app.yandex_web.request
    def queue_request(method,**params):
        if method=='search':
            app.yandex_web.calls.append((method,params));return {'items':[result]}
        return original_request(method,**params)
    with patch.object(app.yandex_web,'request',side_effect=queue_request):
        app.yandex_panel.track_buttons[0].clicked();settle()
    assert ('play',{'id':'123'}) in app.yandex_web.calls
    assert app.music.book.current('yandex-music')['id']=='123'
    assert [v['id'] for _,v in app.music.book.upcoming('yandex-music')]==['456']
    app.yandex_panel.render([{'id':'/playlists/fixture','kind':'playlist','title':'Evening','image':''}])
    app.yandex_panel.track_buttons[0].clicked();settle()
    assert ('tracks',{'id':'/playlists/fixture'}) in app.yandex_web.calls
    assert app.yandex_panel.back.get_visible()
    app.yandex_panel.back.clicked();settle()
    assert app.yandex_panel.category=='collection' and not app.yandex_panel.back.get_visible()
    app.toggle_compact(None);settle(.6)
    assert app.window.get_size().width==320 and app.compact_source.get_label()=='Я⌄'
    app.toggle_compact(None);settle(.6)
    app.select_source('apple-music')
    assert not app.yandex_web.enabled and app.apple_web.enabled
    app.source='apple-music';app.browser_binding='firefox';app.compact=True
    prepared=app.fullscreen
    assert prepared is not None,'Prepare the fullscreen scene before the first click'
    with patch.object(prepared,'open') as opening:
        app.fullscreen_button.clicked();app.show_settings(app.settings_button)
        app.settings.fullscreen_button.clicked()
        assert opening.call_count==2,'Both entry points reuse the prepared scene'
    prepared.close();app.fullscreen=None
    with patch('widget.FullscreenPlayer') as stage:
        app.fullscreen_button.clicked();app.show_settings(app.settings_button)
        app.settings.fullscreen_button.clicked()
        assert stage.call_count==1 and stage.return_value.open.call_count==2
        app.fullscreen=None
    app.show_settings(app.settings_button)
    with patch('widget.widget_restart.service_restart',return_value=True) as restart:
        app.settings.restart_button.clicked()
        assert restart.call_count==1
        assert app.sound.flushed
        app.restart_widget()
        assert restart.call_count==1
    saved=json.loads(widget.STATE.read_text())
    assert saved['source']=='apple-music' and saved['apple_browser']=='firefox' and saved['compact']
    print('PASS settings, restart retention, Apple transitions, Yandex My Wave routing and compact source switching')
finally:
    # Gtk.main() is not entered by this synchronous harness.
    app.frame_health.close()
    app.cover_pause.close()
    app.music.close()
    app.yandex_panel.close();app.yandex_web.close()
    app.accounts.close();app.mpris.close()
    app.youtube_panel.close();app.youtube.close();app.apple.close();app.apple_web.close();app.monitor.close();app.meter.stop();app.sound.close()
    app.artwork.pool.shutdown(wait=False,cancel_futures=True)

