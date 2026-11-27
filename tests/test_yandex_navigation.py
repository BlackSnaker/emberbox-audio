"""Yandex playlist navigation uses the managed queue, not transport flags."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('Gtk','3.0')
from widget import Widget


class NavigationTests(unittest.TestCase):
    def test_managed_previous_and_next_ignore_single_track_transport_flags(self):
        app=Mock()
        app.source='yandex-music';app.resources_closed=False
        state={'authorized':True,'title':'Current','duration':211,'position':0,
               'canPrevious':False,'canNext':False}
        app.native_web.return_value=SimpleNamespace(state=state,connected=True,pid=1,enabled=True,error='')
        app.music.album_listening=False
        app.music.book=SimpleNamespace(active='yandex-music',indices={'yandex-music':1},
            queues={'yandex-music':[{}, {}, {}]},current=lambda source:{'playlistId':'99:1000'})
        app.audio_meter_active.return_value=False
        Widget.render_apple(app)
        app.previous.set_sensitive.assert_called_with(True)
        app.next.set_sensitive.assert_called_with(True)
        # At the end Next still allows the requested playlist-wave handoff.
        app.music.book.indices['yandex-music']=2
        Widget.render_apple(app)
        app.next.set_sensitive.assert_called_with(True)
        # First track: Previous becomes available for restart once time advances.
        app.music.book.indices['yandex-music']=0
        Widget.render_apple(app)
        app.previous.set_sensitive.assert_called_with(False)
        state['position']=4
        Widget.render_apple(app)
        app.previous.set_sensitive.assert_called_with(True)


if __name__=='__main__':unittest.main()
