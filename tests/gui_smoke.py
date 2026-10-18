"""Offline GTK regression checks; never connect to the real player or audio."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
fixture=tempfile.TemporaryDirectory(prefix='emberbox-gui-')
os.environ['XDG_CONFIG_HOME']=str(Path(fixture.name)/'config')
os.environ['XDG_CACHE_HOME']=str(Path(fixture.name)/'cache')
sys.path.insert(0,str(ROOT/'src'))
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib
import widget


def settle():
    deadline=time.monotonic()+.3
    while time.monotonic()<deadline:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.01)

class DummySound:
    def __init__(self,changed):
        self.volume=.6;self.muted=False;self.available=False;self.changed=changed
    def refresh(self,_player):pass
    def set_volume(self,_value):pass
    def toggle_mute(self):pass
    def close(self):pass
widget.SpotifyVolume=DummySound
from sources import Session
class DummyMonitor:
    def __init__(self, connection, changed): self.changed=changed;self.calls=[]
    def poll(self): pass
    def call(self, session, method, args=None, root=False): self.calls.append((session.name,method))
    def close(self): pass
widget.Monitor=DummyMonitor
widget.SpotifyAudioMeter.start=lambda self:None
app=widget.Widget()
try:
    settle()
    assert app.window.get_size().width==460
    app.toggle_compact(None)
    settle()
    assert app.window.get_size().width==320
    assert not app.title.get_visible()
    app.toggle_compact(None)
    settle()
    assert app.window.get_size().width==460
    spotify=Session('org.mpris.MediaPlayer2.spotify', 'Spotify', 'spotify', 1,
        {'PlaybackStatus':'Playing','Metadata':{'xesam:title':'Spotify track'}})
    browser=Session('org.mpris.MediaPlayer2.firefox.instance123', 'Firefox', 'firefox', 2,
        {'PlaybackStatus':'Paused','Metadata':{'xesam:title':'Apple track'}})
    app.on_sessions([spotify,browser])
    assert app.title.get_text()=='Spotify track'
    app.select_source('apple-music',browser)
    assert app.title.get_text()=='Apple track'
    assert app.monitor.calls==[(spotify.name,'Pause')]
    app.on_action(None,'next')
    assert app.monitor.calls[-1]==(browser.name,'Next')
    app.toggle_compact(None)
    settle()
    assert app.window.get_size().width==320
    assert app.compact_source.get_visible()
    app.show_sources(app.compact_source)
    settle()
    assert app.source_picker.popover.get_visible()
    app.source_picker.popover.popdown()
    app.toggle_compact(None)
    settle()
    app.select_source('spotify')
    assert app.title.get_text()=='Spotify track'
    assert not app.source_picker.popover.get_visible()
    app.expanded=True;app.apply_layout()
    app.select_source('apple-music',browser)
    assert not app.drawer.get_reveal_child()
    assert app.discovery_name.get_text()=='♫  Apple Music'
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
    print('PASS compact layout and non-recursive category switching')
finally:
    # Gtk.main() is not entered by this synchronous harness.
    app.meter.stop();app.sound.close()
    app.artwork.pool.shutdown(wait=False,cancel_futures=True)

