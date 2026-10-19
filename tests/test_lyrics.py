"""Lyrics remain optional and cannot stall or overwrite a new playing track."""
from pathlib import Path
import sys
import tempfile
import threading
import time
from unittest.mock import patch
import unittest
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from gi.repository import GLib
from lyrics import LyricsClient, LyricsState, LyricLine, active_line, parse_lrc


def drain_until(predicate, timeout=2):
    context = GLib.MainContext.default()
    until = time.monotonic()+timeout
    while time.monotonic()<until:
        while context.pending():
            context.iteration(False)
        if predicate():
            return True
        time.sleep(.005)
    return False


def record(title='Fixture', duration=180, synced='[00:01.00]Ember fixture\n[00:03.50]Gentle glow'):
    return {'id': 1, 'trackName': title, 'artistName': 'Fixture artist',
            'albumName': 'Fixture album', 'duration': duration,
            'instrumental': False, 'syncedLyrics': synced, 'plainLyrics': None}


class LyricsTests(unittest.TestCase):
    def test_lrc_repeated_lines_offsets_gaps_and_seek_index(self):
        parsed = parse_lrc('[ar:Synthetic artist]\n[offset:500]\n'
                           '[00:01.00][00:05.000]<00:01.00>Ember fixture\n'
                           '[00:03.50]\n[00:05.000]Перевод\nmalformed line')
        self.assertEqual(parsed, (LyricLine(.5, 'Ember fixture'), LyricLine(3., ''),
                                  LyricLine(4.5, 'Ember fixture\nПеревод')))
        self.assertEqual(active_line(parsed, 0), -1)
        self.assertEqual(active_line(parsed, .5), 0)
        self.assertEqual(active_line(parsed, 4), 1)
        self.assertEqual(active_line(parsed, 6), 2)
        self.assertEqual(active_line(parsed, 1), 0)  # Seeking backwards.
        self.assertEqual(active_line(parsed, float('nan')), -1)

    def test_slow_old_request_never_blocks_gui_or_replaces_new_track(self):
        entered, release = threading.Event(), threading.Event()
        main_thread = threading.get_ident()
        callbacks, calls = [], []
        with tempfile.TemporaryDirectory() as folder:
            client = LyricsClient(lambda: callbacks.append((threading.get_ident(), client.state)), folder)
            def request(endpoint, params, generation):
                calls.append(params['track_name'])
                if params['track_name'] == 'Slow fixture':
                    entered.set();release.wait(2)
                return record(params['track_name'])
            try:
                with patch.object(client, '_request', side_effect=request):
                    started = time.monotonic()
                    client.set_track('Slow fixture', 'Fixture artist', duration=180)
                    self.assertLess(time.monotonic()-started, .1)
                    self.assertTrue(entered.wait(1))
                    client.set_track('New fixture', 'Fixture artist', duration=180)
                    self.assertTrue(drain_until(lambda: bool(callbacks)))
                    self.assertTrue(all(state.status=='loading' for _, state in callbacks))
                    release.set()
                    self.assertTrue(drain_until(lambda: client.state.status=='ready'))
                    self.assertEqual(client.key[0], 'New fixture')
                    self.assertEqual(calls, ['Slow fixture', 'New fixture'])
                    self.assertTrue(all(ident==main_thread for ident, _ in callbacks))
                    self.assertEqual(sum(state.status=='ready' for _, state in callbacks), 1)
                    # Repeated 60 Hz render updates must not trigger another lookup.
                    for _ in range(120):
                        client.set_track('New fixture', 'Fixture artist', duration=180)
                    self.assertEqual(calls, ['Slow fixture', 'New fixture'])
            finally:
                release.set();client.close()

    def test_close_during_request_is_immediate_and_suppresses_late_callback(self):
        entered, release = threading.Event(), threading.Event()
        changes = []
        with tempfile.TemporaryDirectory() as folder:
            client = LyricsClient(lambda: changes.append(client.state.status), folder)
            def request(*args):
                entered.set();release.wait(2)
                return record()
            with patch.object(client, '_request', side_effect=request):
                client.set_track('Fixture', 'Fixture artist')
                self.assertTrue(entered.wait(1))
                started = time.monotonic();client.close()
                self.assertLess(time.monotonic()-started, .1)
                release.set()
                client.future.result(timeout=1)
                drain_until(lambda: False, .03)
                self.assertEqual(changes, [])

    def test_plain_instrumental_missing_and_private_disk_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            client = LyricsClient(lambda: None, folder)
            try:
                with patch.object(client, '_request', return_value={**record(synced=None), 'plainLyrics': 'Synthetic words\nAmber light'}):
                    client.set_track('Fixture', 'Fixture artist', duration=180)
                    self.assertTrue(drain_until(lambda: client.state.status=='ready'))
                    self.assertFalse(client.state.synced)
                    self.assertEqual(client.state.plain, 'Synthetic words\nAmber light')
                cached = list(Path(folder).glob('*.json'))
                self.assertEqual(len(cached), 1)
                self.assertEqual(cached[0].stat().st_mode&0o777, 0o600)
                client.set_track('', '')
                with patch.object(client, '_request') as request:
                    client.set_track('Fixture', 'Fixture artist', duration=180)
                    self.assertTrue(drain_until(lambda: client.state.status=='ready'))
                    request.assert_not_called()
                for title, returned, expected in [('Instrumental', {'instrumental': True}, 'instrumental'),
                                                  ('Unavailable', None, 'missing')]:
                    with patch.object(client, '_request', return_value=returned):
                        client.set_track(title, 'Fixture artist')
                        self.assertTrue(drain_until(lambda: client.state.status==expected))
            finally:
                client.close()
            second = LyricsClient(lambda: None, folder)
            try:
                with patch.object(second, '_request') as request:
                    second.set_track('Fixture', 'Fixture artist', duration=180)
                    self.assertTrue(drain_until(lambda: second.state.status=='ready'))
                    request.assert_not_called()
            finally:
                second.close()

    def test_synced_cache_preserves_simultaneous_translation_and_silent_gap(self):
        with tempfile.TemporaryDirectory() as folder:
            client = LyricsClient(lambda: None, folder)
            value = LyricsState('ready', (LyricLine(1., 'Synthetic fixture\nПеревод'), LyricLine(2.5, '')),
                                'Synthetic fixture\nПеревод')
            key = ('Fixture', 'Fixture artist', '', 180)
            try:
                client._save(key, value)
                self.assertEqual(client._cached(key), value)
            finally:
                client.close()

    def test_search_rejects_wrong_artist_and_wrong_recording_duration(self):
        values = [record(title='Fixture (feat. Guest)', duration=198),
                  {**record(), 'artistName': 'Different artist'},
                  record(duration=181)]
        with tempfile.TemporaryDirectory() as folder:
            client = LyricsClient(lambda: None, folder)
            try:
                with patch.object(client, '_request', side_effect=[None, values]) as request:
                    client.set_track('Fixture (feat. Guest)', 'Fixture artist', 'Fixture album', 180)
                    self.assertTrue(drain_until(lambda: client.state.status=='ready'))
                    self.assertEqual(client.state.lines[0].text, 'Ember fixture')
                    self.assertEqual(request.call_args_list[1].args[1]['track_name'], 'Fixture')
                with patch.object(client, '_request', side_effect=[None, values[:2]]):
                    client.set_track('Fixture', 'Fixture artist', duration=180)
                    self.assertTrue(drain_until(lambda: client.state.status=='missing'))
            finally:
                client.close()

    def test_rate_limit_respects_retry_after_and_does_not_search(self):
        with tempfile.TemporaryDirectory() as folder:
            client = LyricsClient(lambda: None, folder)
            try:
                error = urllib.error.HTTPError('https://lrclib.net/api/get', 429, 'Limit', {'Retry-After': '37'}, None)
                with patch('lyrics.urllib.request.urlopen', side_effect=error) as request:
                    client.set_track('Fixture', 'Fixture artist')
                    self.assertTrue(drain_until(lambda: client.state.status=='error'))
                    self.assertGreater(client.next_request-time.monotonic(), 35)
                    self.assertEqual(request.call_count, 1)
                    headers = dict(request.call_args.args[0].header_items())
                    self.assertIn('Emberbox', headers['User-agent'])
                    self.assertEqual(headers['Accept'], 'application/json')
            finally:
                client.close()


if __name__ == '__main__':
    unittest.main()
