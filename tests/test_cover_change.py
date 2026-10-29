"""Cover transitions follow transport facts without owning the transport."""
from pathlib import Path
from types import ModuleType, SimpleNamespace
import importlib.util
import sys
import unittest
from unittest.mock import Mock, patch

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))
from listening_queue import track


class Ripple:
    """Record the visual boundary; GTK, GL and clocks are deliberately absent."""
    def __init__(self):
        self.active = False
        self.pixels = None
        self.begun = []
        self.supplied = []
        self.resolved = 0
        self.closed = False

    def begin(self, pixels):
        self.active = pixels is not None
        self.pixels = pixels
        self.begun.append(pixels)
        return self.active

    def get_pixbuf(self):
        return self.pixels

    def supply(self, pixels):
        self.supplied.append(pixels)

    def resolve(self):
        self.resolved += 1

    def cancel(self):
        self.active = False
        self.pixels = None

    def close(self):
        self.cancel()
        self.closed = True


def load_controller():
    # The real library module starts GTK/source imports. Its snapshot boundary
    # is a plain mapping here, with the same IDs/URIs as normalized queue items.
    library = ModuleType('music_library')
    library.snapshot = lambda host: dict(host.snapshot)
    ripple = ModuleType('cover_ripple')
    ripple.CoverRipple = Ripple
    spec = importlib.util.spec_from_file_location('cover_change_under_test', SRC / 'cover_change.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'music_library': library, 'cover_ripple': ripple}):
        spec.loader.exec_module(module)
    return module


controller = load_controller()


class CoverChangeTests(unittest.TestCase):
    def setUp(self):
        self.clock = 100.
        self.clock_patch = patch.object(controller.time, 'monotonic', side_effect=lambda: self.clock)
        self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)
        self.old_art, self.new_art, self.third_art = object(), object(), object()
        self.art = self.old_art
        self.host = SimpleNamespace(
            source='apple-music', apple_mode='native', youtube_mode='native',
            playing=True, length=180_000_000, art_url='album-a.jpg',
            apple_web=SimpleNamespace(state={'spatial': {'enabled': True, 'phase': 'playing', 'switching': False}}),
            youtube=SimpleNamespace(loaded=True, loading=False, failed=False, error=''),
        )
        self.transport = [Mock(side_effect=AssertionError('A cover animation must never invoke playback')) for _ in range(5)]
        for name, method in zip(('play', 'pause', 'next', 'previous', 'seek'), self.transport):
            setattr(self.host, name, method)
        self.first = self.item('101', 'First song')
        self.second = self.item('102', 'Second song')
        self.third = self.item('103', 'Third song')
        self.current = self.first
        self.music = SimpleNamespace(play_generation=0, loading=False, error='',
                                     book=SimpleNamespace(active='apple-music', current=lambda source: self.current))
        self.stage = SimpleNamespace(host=self.host, music=self.music, visible=True, closed=False,
                                     page='playing', reveal=SimpleNamespace(active=False),
                                     cover=SimpleNamespace(get_pixbuf=lambda: self.art),
                                     motion_image=SimpleNamespace(get_pixbuf=lambda: None))
        self.layers = SimpleNamespace(add_overlay=Mock(), set_overlay_pass_through=Mock())
        self.change = controller.CoverChange(self.stage, self.layers)
        self.select(self.first)
        self.change.observe()
        self.addCleanup(self.assert_transport_untouched)

    @staticmethod
    def item(ident, title):
        return track({'uri': 'apple:songs:' + ident, 'title': title, 'artist': 'One Artist',
                      'album': 'Shared album'}, 'apple-music')

    def select(self, item, *, ready=True, art_url=None):
        self.host.snapshot = dict(item, valid=True, playing=self.host.playing,
                                  duration=self.host.length / 1e6)
        self.host.apple_web.state.update(id=item['id'], catalogId=item['id'])
        self.host.apple_web.state['spatial'].update(phase='playing' if ready else 'preparing', switching=not ready)
        if art_url is not None:
            self.host.art_url = art_url

    def queue(self, item):
        self.current = item
        self.music.play_generation += 1
        self.music.loading = True
        self.change.queue_changed()

    def assert_transport_untouched(self):
        for method in self.transport:
            method.assert_not_called()

    def test_queue_selection_starts_on_old_cover_before_transport_metadata_moves(self):
        self.queue(self.second)
        self.assertEqual(self.host.snapshot['id'], self.first['id'])
        self.assertEqual(self.change.surface.begun, [self.old_art])
        self.assertTrue(self.change.surface.active)
        self.change.observe()
        self.assertEqual(self.change.surface.resolved, 0)

    def test_apple_playing_flag_cannot_finish_preparing_or_switching(self):
        self.queue(self.second)
        self.select(self.second, ready=False, art_url='album-b.jpg')
        self.art = self.new_art
        self.change.art_ready(self.new_art, 'album-b.jpg')
        self.change.observe()
        self.assertTrue(self.host.playing)
        self.assertEqual(self.change.surface.resolved, 0)
        self.host.apple_web.state['spatial'].update(phase='playing', switching=True)
        self.change.observe()
        self.assertEqual(self.change.surface.resolved, 0)
        self.host.apple_web.state['spatial']['switching'] = False
        self.change.observe()
        self.assertEqual(self.change.surface.resolved, 1)
        self.assertIs(self.change.surface.supplied[-1], self.new_art)

    def test_ready_transport_waits_for_matching_cover_callback_and_rejects_stale_url(self):
        self.queue(self.second)
        self.select(self.second, art_url='album-b.jpg')
        self.change.observe()
        self.assertEqual(self.change.surface.resolved, 0)
        self.change.art_ready(self.old_art, 'album-a.jpg')
        self.assertEqual(self.change.surface.supplied, [])
        self.art = self.new_art
        self.change.art_ready(self.new_art, 'album-b.jpg')
        self.change.observe()
        self.assertEqual(self.change.surface.resolved, 1)
        self.assertTrue(all(value is self.new_art for value in self.change.surface.supplied))

    def test_same_album_cover_still_animates_when_track_identity_changes(self):
        self.change.art_ready(self.old_art, 'album-a.jpg')
        self.queue(self.second)
        self.assertEqual(len(self.change.surface.begun), 1)
        self.select(self.second)
        self.change.observe()
        self.assertEqual(self.change.surface.resolved, 1)
        self.assertIs(self.change.surface.supplied[-1], self.old_art)

    def test_automatic_track_change_animates_without_queue_request(self):
        self.select(self.second, ready=False, art_url='album-b.jpg')
        self.change.observe()
        self.assertEqual(self.change.surface.begun, [self.old_art])
        self.assertEqual(self.change.surface.resolved, 0)
        self.art = self.new_art
        self.change.art_ready(self.new_art, 'album-b.jpg')
        self.host.apple_web.state['spatial'].update(phase='playing', switching=False)
        self.change.observe()
        self.assertEqual(self.change.surface.resolved, 1)

    def test_latest_rapid_selection_wins_and_intermediate_cover_is_not_supplied(self):
        self.queue(self.second)
        self.queue(self.third)
        self.assertEqual(len(self.change.surface.begun), 2)
        self.select(self.second, art_url='album-b.jpg')
        self.change.observe()
        self.change.art_ready(self.new_art, 'album-b.jpg')
        self.assertEqual(self.change.surface.supplied, [])
        self.assertEqual(self.change.surface.resolved, 0)
        self.select(self.third, art_url='album-c.jpg')
        self.art = self.third_art
        self.change.observe()
        self.change.art_ready(self.third_art, 'album-c.jpg')
        self.change.observe()
        self.assertEqual(self.change.surface.resolved, 1)
        self.assertTrue(all(value is self.third_art for value in self.change.surface.supplied))

    def test_superseded_generation_without_a_new_loading_request_cleans_up(self):
        self.queue(self.second)
        self.music.play_generation += 1
        self.music.loading = False
        self.change.queue_changed()
        self.assertFalse(self.change.surface.active)

    def test_queue_error_cancels_even_before_metadata_changes(self):
        self.queue(self.second)
        self.music.error = 'The selected song could not be loaded'
        self.change.observe()
        self.assertFalse(self.change.surface.active)

    def test_apple_switch_error_cancels_manual_request_before_metadata_changes(self):
        self.change.request()
        self.host.apple_web.state['spatial']['switchError'] = {'id': self.second['id'], 'code': 'decoder failed'}
        self.change.observe()
        self.assertFalse(self.change.surface.active)

    def test_old_or_unrelated_apple_error_does_not_cancel_new_selection(self):
        spatial = self.host.apple_web.state['spatial']
        spatial['switchError'] = {'id': self.first['id'], 'code': 'old failure'}
        self.queue(self.third)
        self.change.observe()
        self.assertTrue(self.change.surface.active)
        spatial['switchError'] = {'id': self.second['id'], 'code': 'superseded failure'}
        self.change.observe()
        self.assertTrue(self.change.surface.active)
        spatial['switchError'] = {'id': self.third['id'], 'code': 'requested song failed'}
        self.change.observe()
        self.assertFalse(self.change.surface.active)

    def test_stopped_transport_cleans_up_pending_visual(self):
        self.queue(self.second)
        self.music.loading = False
        self.host.playing = False
        self.host.length = 0
        self.host.snapshot = {'valid': False, 'playing': False, 'title': '', 'artist': '', 'id': '', 'uri': ''}
        self.change.observe()
        self.assertFalse(self.change.surface.active)

    def test_temporary_empty_metadata_during_loading_is_not_mistaken_for_stop(self):
        self.queue(self.second)
        self.host.playing = False
        self.host.length = 0
        self.host.snapshot = {'valid': False, 'playing': False, 'title': '', 'artist': '', 'id': '', 'uri': ''}
        self.change.observe()
        self.assertTrue(self.change.surface.active)
        self.music.loading = False
        self.host.apple_web.state['spatial']['phase'] = 'preparing'
        self.change.observe()
        self.assertTrue(self.change.surface.active)

    def test_source_change_cleans_up_and_late_cover_cannot_restart_animation(self):
        self.queue(self.second)
        self.host.source = 'spotify'
        self.change.observe()
        self.assertFalse(self.change.surface.active)
        self.change.art_ready(self.new_art, 'album-a.jpg')
        self.assertEqual(self.change.surface.supplied, [])

    def test_hidden_closed_or_other_page_cleans_up_and_ignores_new_requests(self):
        for field, value in (('visible', False), ('closed', True), ('page', 'queue')):
            with self.subTest(field=field):
                previous = getattr(self.stage, field)
                self.change.request()
                self.assertTrue(self.change.surface.active)
                setattr(self.stage, field, value)
                self.change.observe()
                self.assertFalse(self.change.surface.active)
                count = len(self.change.surface.begun)
                self.change.request()
                self.assertEqual(len(self.change.surface.begun), count)
                setattr(self.stage, field, previous)

    def test_previous_restarting_same_track_does_not_wait_indefinitely(self):
        self.change.request()
        self.clock += 3.49
        self.change.observe()
        self.assertTrue(self.change.surface.active)
        self.clock += .02
        self.change.observe()
        self.assertFalse(self.change.surface.active)
        self.assertEqual(self.change.surface.resolved, 0)

    def test_manual_apple_switch_preparing_can_exceed_same_track_restart_timeout(self):
        self.change.request()
        self.host.apple_web.state['spatial'].update(phase='preparing', switching=True)
        self.clock += 4.
        self.change.observe()
        self.assertTrue(self.change.surface.active)
        self.assertEqual(self.change.surface.resolved, 0)
        self.select(self.second, art_url='album-b.jpg')
        self.art = self.new_art
        self.change.art_ready(self.new_art, 'album-b.jpg')
        self.change.observe()
        self.assertEqual(self.change.surface.resolved, 1)

    def test_selecting_current_song_cancels_an_older_pending_change(self):
        self.queue(self.second)
        self.assertTrue(self.change.surface.active)
        self.queue(self.first)
        self.assertFalse(self.change.surface.active)
        self.assertEqual(self.change.surface.resolved, 0)
        self.assertEqual(len(self.change.surface.begun), 1)

    def test_failed_cover_cdn_has_bounded_wait_after_audio_ready(self):
        self.queue(self.second)
        self.select(self.second, art_url='album-b.jpg')
        self.change.observe()
        self.clock += 2.99
        self.change.observe()
        self.assertEqual(self.change.surface.resolved, 0)
        self.clock += .02
        self.change.observe()
        self.assertEqual(self.change.surface.resolved, 1)

    def test_close_releases_surface_and_late_callbacks_do_not_supply(self):
        self.queue(self.second)
        self.change.close()
        self.assertTrue(self.change.surface.closed)
        self.assertFalse(self.change.surface.active)
        self.change.art_ready(self.new_art, 'album-a.jpg')
        self.assertEqual(self.change.surface.supplied, [])


if __name__ == '__main__':
    unittest.main()
