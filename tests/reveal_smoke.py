"""Exercise the real shader and room capture with isolated, original fixtures."""
from unittest.mock import patch
import fullscreen_smoke as fixture
import fullscreen

host=fixture.FixtureHost()
with patch.object(fullscreen,'LyricsClient',fixture.FixtureLyrics),patch.object(fullscreen.Artwork,'load',fixture.image_load):
    stage=fullscreen.FullscreenPlayer(host)
    try:
        stage.prewarm()
        if not stage.reveal.driver:
            stage.reveal.error=''
            stage.reveal.warmup(host.cover.get_pixbuf(),allow_software=True)
        if not stage.reveal.driver:
            print('SKIP GL unavailable; compositor fallback is covered by fullscreen_smoke.py')
        else:
            frames=[]
            original=stage.reveal.driver.draw
            def draw(*args,**kwargs):
                frames.append((stage.layout.get_mapped(),stage.background.get_mapped(),stage.reveal.room is not None,
                               stage.reveal.previous is not None,stage.reveal.reversing))
                return original(*args,**kwargs)
            stage.reveal.driver.draw=draw
            stage.open()
            assert stage.reveal.room is not None,'Prepare a single room texture before moving'
            fixture.settle(1.4)
            assert len(frames)>=2,frames
            assert all(not row[0] and not row[1] and row[2] for row in frames),frames
            assert not stage.reveal.active and stage.layout.get_mapped()
            assert not stage.lyrics_visible
            assert not any(call[0] for call in stage.lyrics.calls)
            assert host.calls==[],'An entrance must not send playback commands'
            point=stage.cover.translate_coordinates(stage.window,0,0)
            cover_rect=(*point,stage.cover.get_allocated_width(),stage.cover.get_allocated_height())
            stage.lyrics_button.clicked()
            assert stage.reveal.cover_origin==cover_rect,'GTK margins must not offset the moving cover'
            fixture.wait_transition(stage)
            assert stage.lyrics_visible and stage.line_buttons
            stage.lyrics_button.clicked();fixture.wait_transition(stage)
            assert not stage.lyrics_visible and any(row[3] for row in frames)
            stage.dismiss();fixture.wait_transition(stage)
            assert not stage.visible and any(row[4] for row in frames)
            assert stage.reveal.room is None and stage.reveal.cover_pixels is None
            assert host.calls==[],'Visual transitions must preserve playback'
            host.window.hide()
            stage.open();fixture.wait_transition(stage)
            stage.dismiss()
            assert stage.reveal.cover_origin is not None,'An unmapped desktop widget still needs a safe return target'
            with patch.object(stage.reveal.driver,'draw',side_effect=RuntimeError('fixture GPU failure')):
                fixture.wait_transition(stage)
            assert not stage.visible,'A lost GL frame must not strand the fullscreen window'
            print('PASS shader, owned snapshots, lyrics morph, reverse entrance, zero live GTK paints and cleanup')
    finally:
        stage.close();host.window.destroy()
