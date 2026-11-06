"""Real in-playlist transition desk at three sizes, without network/audio."""
import os,time
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import fullscreen_smoke as f
import fullscreen
from gi.repository import Gtk,Gdk,GLib
from seasonal_theme import Appearance
from flow_plans import playlist_key


def settle(seconds=.15):
    until=time.monotonic()+seconds;c=GLib.MainContext.default()
    while time.monotonic()<until:
        for _ in range(2):
            if c.pending():c.iteration(False)
        time.sleep(.002)


def wait(predicate):
    until=time.monotonic()+4
    while not predicate() and time.monotonic()<until:settle(.04)
    assert predicate()


def fits(stage,widgets):
    width,height=stage.window.get_size()
    for child in widgets:
        assert child.get_mapped(),type(child).__name__
        x,y=child.translate_coordinates(stage.window,0,0);a=child.get_allocation()
        assert x>=0 and y>=0 and x+a.width<=width+2 and y+a.height<=height+2,(type(child).__name__,x,y,a.width,a.height,width,height)


items=[dict(uri=f'apple:songs:{100+i}',id=str(100+i),kind='songs',title=name,
            artist='Emberbox Sessions',image='fixture:cover',duration_ms=180000+i*8000)
       for i,name in enumerate(('Afterglow','Amber Lines','Night Drive','Тёплый воздух'))]
playlist=dict(uri='apple:library-playlists:p.fixture',kind='library-playlists',id='p.fixture',title='Slow Evenings',image='fixture:cover')
host=f.FixtureHost();host.source='apple-music';host.apple_web=SimpleNamespace(state={'emberFlow':True,'emberBeatSync':False})
host.appearance=Appearance();host.appearance.set_theme('nocturne');host.settings.appearance=host.appearance
with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected network')),\
     patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),patch.object(fullscreen.Artwork,'load',f.image_load):
    stage=fullscreen.FullscreenPlayer(host);host.fullscreen=stage
    service=stage.music;service.repository.load=lambda *a,**k:{'tracks':items}
    try:
        stage.open();f.wait_transition(stage);stage.page_tabs['library'].clicked()
        view=stage.library_view;view.open_collection(playlist);wait(lambda:len(view.song_buttons)==4)
        assert view.transition_button.get_visible();view.transition_button.clicked();settle(.3);desk=view.editor
        assert desk and not service.book.active,'Opening editor started playback'
        before=service.book.revision
        desk.mode.set_active_id('manual');desk.length.set_value(4.5);desk.shape.set_active_id('smooth');settle()
        key=playlist_key('apple-music',playlist)
        assert service.flow.plans.get(key,items[0],items[1])['seconds']==4.5
        assert service.book.revision==before,'Editing changed playback queue'
        desk.pairs.set_active(1);assert desk.mode.get_active_id()=='auto'
        desk.pairs.set_active(0);assert desk.length.get_value()==4.5
        desk.auto_button.clicked();assert len(service.flow.plans.data[key])==3
        assert all(v['mode']=='auto' for v in service.flow.plans.data[key].values())
        assert not desk.beats.get_sensitive(),'Native Atmos/Lossless falsely offered beat sync'
        # Real dial, keyboard and metal switch signals save without touching playback.
        desk.mode_buttons['manual'].clicked();desk.length.set_value(4.5)
        event=Gdk.Event.new(Gdk.EventType.KEY_PRESS);event.keyval=Gdk.KEY_Up;event.state=Gdk.ModifierType(0)
        desk.knob.emit('key-press-event',event);assert desk.length.get_value()==5
        desk.shape_buttons['smooth'].clicked();assert desk.shape.get_active_id()=='smooth'
        assert desk.graph.get_transition_running() or not Gtk.Settings.get_default().get_property('gtk-enable-animations')
        settle(.5);assert not desk.graph.get_transition_running() and desk.knob.tick==0
        service.flow.set_enabled(True);settle(.8)
        target=os.environ.get('EMBERBOX_FLOW_EDITOR_PREVIEW')
        for width,height in ((1920,1080),(1280,720),(1024,600)):
            stage.window.unfullscreen();stage.window.resize(width,height);settle(.4)
            assert stage.window.get_size()==(width,height),(stage.window.get_size(),width,height)
            fits(stage,[desk.pairs,desk.auto_button,desk.preview_button,stage.play_button,stage.knob])
            if target and width==1920:
                path=Path(target);path.mkdir(parents=True,exist_ok=True)
                Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,width,height).savev(str(path/'flow-editor.png'),'png',[],[])
        # Unsupported sources keep edits, but never pretend mixing is available.
        host.source='spotify';desk.sync();assert not desk.preview_button.get_sensitive()
        host.source='apple-music';view.close_editor();settle();assert view.editor is None
        assert len(view.song_buttons)==4
        annotated=view.songs();assert all(v['flow_playlist']==key for v in annotated)
        view.open_transitions();settle();view.deactivate();assert view.editor is None
        print('PASS playlist transition editor, isolated recipes, adaptive batch, honest capabilities, three sizes and lifecycle')
    finally:stage.close();host.window.destroy()
