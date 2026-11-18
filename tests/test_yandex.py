from pathlib import Path
import io
import json
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import yandex_web
from yandex_api import API, YandexError, NoRedirect, safe_url, token_store, track
from stream_target import Target, matches


RAW = {'id': '12', 'title': 'Song', 'durationMs': 120000,
       'artists': [{'id': 7, 'name': 'Artist'}],
       'albums': [{'id': 8, 'title': 'Album'}], 'coverUri': 'avatars.yandex.net/%%'}


def player():
    app = yandex_web.YandexWeb.__new__(yandex_web.YandexWeb)
    app.changed = Mock()
    app.lock = threading.RLock()
    app.playback_lock = threading.RLock()
    app.api = Mock()
    app.uid = '42'
    app.enabled = True
    app.closed = False
    app.state = {'authorized': True, 'ready': True}
    app.queue = []
    app.index = -1
    app.session = app.batch = ''
    app.mpv = Mock(pause=True)
    app.error = ''
    return app


class YandexTests(unittest.TestCase):
    def test_disabled_source_never_starts_playback(self):
        app = player()
        app.enabled = False
        for method, params in [('wave', {}), ('play', {'id': '12'}), ('transport', {'action': 'play'})]:
            self.assertEqual(app.request(method, **params), {'skipped': True})
        app.api.call.assert_not_called()
        app.api.stream.assert_not_called()
        app.mpv.play.assert_not_called()

    def test_source_can_be_disabled_while_stream_request_is_pending(self):
        app = player()
        def resolve(_ident):
            app.set_enabled(False)
            return 'https://storage.yandex.net/audio'
        app.api.stream.side_effect = resolve
        self.assertEqual(app._play(track(RAW)), {'skipped': True})
        app.mpv.play.assert_not_called()
        self.assertTrue(app.mpv.pause)

    def test_direct_id_playback_and_seek(self):
        app = player()
        app.api.tracks.return_value = [RAW]
        app.api.stream.return_value = 'https://storage.yandex.net/audio'
        app.request('play', id='12')
        app.api.tracks.assert_called_once_with(['12'])
        app.api.stream.assert_called_once_with('12')
        app.mpv.play.assert_called_once_with('https://storage.yandex.net/audio')
        self.assertFalse(app.mpv.pause)
        self.assertEqual(app.state['albumId'], '8')
        self.assertFalse(app.state['ended'])
        app.request('seek', position=999)
        app.mpv.seek.assert_called_once_with(120, 'absolute+exact')
        app.request('transport', action='pause')
        self.assertTrue(app.mpv.pause)
        app.request('transport', action='play')
        self.assertFalse(app.mpv.pause)

    def test_wave_uses_session_api_and_refills_after_finish(self):
        app = player()
        app.api.call.side_effect = [
            {'radioSessionId': 'session', 'batchId': 'batch', 'sequence': [{'track': RAW}]},
            {}, {}, {},
            {'radioSessionId': 'session', 'batchId': 'batch2', 'sequence': [{'track': dict(RAW, id='13')}]},
            {}]
        app.request('wave')
        self.assertTrue(app.state['wave'])
        self.assertTrue(app.state['canNext'])
        self.assertEqual(app.api.call.call_args_list[0].args, ('rotor/session/new',))
        app.request('_ended')
        self.assertEqual(app.state['id'], '13')
        events = [c.kwargs['json_body']['event']['type'] for c in app.api.call.call_args_list
                  if c.args[0].endswith('/feedback')]
        self.assertEqual(events, ['radioStarted', 'trackStarted', 'trackFinished', 'trackStarted'])

    def test_end_of_single_track_signals_managed_queue(self):
        app = player()
        app.queue = [track(RAW)]
        app.index = 0
        app.request('_ended')
        self.assertTrue(app.state['ended'])
        self.assertFalse(app.state['playing'])

    def test_next_at_end_does_not_claim_current_audio_stopped(self):
        app = player()
        app.queue = [track(RAW)]
        app.index = 0
        app.state['playing'] = True
        app.request('transport', action='next')
        self.assertTrue(app.state['playing'])

    def test_playlist_tracks_resolve_missing_metadata(self):
        app = player()
        app.api.call.return_value = {'tracks': [{'id': '12'}, {'track': dict(RAW, id='13')}]}
        app.api.tracks.return_value = [RAW]
        result = app.request('tracks', id='42:10')
        self.assertEqual([v['id'] for v in result['items']], ['12', '13'])
        self.assertEqual([v['playlistId'] for v in result['items']], ['42:10', '42:10'])
        from listening_queue import track as queue_track
        self.assertEqual(queue_track(result['items'][0], 'yandex-music')['playlistId'], '42:10')
        self.assertNotIn('playlistId', queue_track(dict(result['items'][0], playlistId='invalid'), 'yandex-music'))
        app.api.call.assert_called_once_with('users/42/playlists/10')

    def test_managed_playlist_queue_is_used_instead_of_transport_single_track(self):
        app = player()
        app.queue = [dict(track(RAW), title='Avalon Dust')]
        expected = [dict(track(RAW), title='Avalon Dust'),
                    dict(track(RAW), id='13', title='London Bridge Is Falling Down My Fair Lady')]
        app.queue_provider = Mock(return_value=expected)
        self.assertEqual(app.request('browse', category='queue')['items'], expected)
        app.api.call.assert_not_called()
        # Rotor owns its own queue; a previous managed playlist must not leak in.
        app.session = 'wave-session'
        self.assertEqual(app.request('browse', category='queue')['items'], app.queue)
        app.queue_provider.assert_called_once()

    def test_unmanaged_transport_queue_is_still_available(self):
        app = player()
        app.queue = [track(RAW)]
        app.queue_provider = Mock(return_value=None)
        self.assertEqual(app.request('browse', category='queue')['items'], app.queue)

    def test_like_confirmation_and_remove(self):
        app = player()
        self.assertEqual(app.request('favorite', id='12', value=False), {'confirmed': True, 'favorite': False})
        app.api.call.assert_called_once_with('users/42/likes/tracks/remove', {'track-ids': '12'})

    def test_failed_token_storage_restores_current_account(self):
        app = player()
        old_api = app.api
        old_state = dict(app.state)
        with patch('yandex_web.API') as factory, patch('yandex_web.token_store', side_effect=YandexError('Locked keyring')):
            factory.return_value.call.return_value = {'account': {'uid': '99'}}
            with self.assertRaises(YandexError):
                app._save_token('new-token')
        self.assertIs(app.api, old_api)
        self.assertEqual(app.uid, '42')
        self.assertEqual(app.state, old_state)
        app.mpv.command.assert_not_called()

    def test_yandex_spectrum_does_not_capture_other_apps(self):
        target = Target('yandex-music', 12345, '', 'yandex-native')
        with patch('stream_target.descendant', side_effect=lambda pid, owner: pid == owner), \
             patch.object(Path, 'resolve', return_value=Path('/engine/EmberboxYandex')):
            self.assertTrue(matches({'application.process.id': '12345'}, target))
            self.assertFalse(matches({'application.process.id': '444', 'application.name': 'Spotify'}, target))


class PersonalPlaylistTests(unittest.TestCase):
    def test_personal_playlists_keep_server_titles_and_foreign_owner(self):
        app = player()
        day = {'kind': 1000, 'owner': {'uid': 99}, 'title': 'Плейлист дня'}
        week = {'kind': 1001, 'uid': 98, 'title': 'Премьера'}
        app.api.call.return_value = {'blocks': [{'entities': [
            {'data': {'ready': True, 'data': day}},
            {'data': {'ready': True, 'data': week}},
            {'data': {'ready': True, 'data': day}},
            {'data': {'ready': False, 'data': dict(day, kind=1002)}},
            {'data': {'ready': True, 'data': {'title': 'Not a playlist'}}}]}]}
        result = app.request('browse', category='personal')
        self.assertEqual([(v['id'], v['title']) for v in result['items']],
                         [('99:1000', 'Плейлист дня'), ('98:1001', 'Премьера')])
        app.api.call.assert_called_once_with('landing3', blocks='personalplaylists')
        app.api.call.reset_mock()
        app.api.call.return_value = {'tracks': []}
        app.request('tracks', id=result['items'][0]['id'])
        app.api.call.assert_called_once_with('users/99/playlists/1000')

    def test_no_personal_playlists_has_note_not_fake_cards(self):
        app = player()
        app.api.call.return_value = {'blocks': []}
        result = app.request('browse', category='personal')
        self.assertEqual(result['items'], [])
        self.assertTrue(result['note'])

    def test_next_after_finished_playlist_track_starts_wave_and_clears_context(self):
        app = player()
        app.api.tracks.return_value = [RAW]
        app.request('play', id='12', playlistId='99:1000')
        self.assertTrue(app.state['canNext'])
        app.request('_ended')
        self.assertTrue(app.state['ended'])
        self.assertFalse(app.session)
        app.api.call.side_effect = [
            {'radioSessionId': 'continued', 'batchId': 'b', 'sequence': [{'track': RAW}]}, {}, {}]
        app.request('transport', action='next')
        self.assertEqual(app.api.call.call_args_list[0].kwargs['json_body']['seeds'], ['playlist:99_1000'])
        self.assertEqual(app.state['playlistId'], '')
        self.assertTrue(app.state['wave'])

    def test_track_wave_keeps_its_origin_across_refill_and_clears_on_direct_play(self):
        app=player()
        app.api.call.side_effect=[
            {'radioSessionId':'track-session','batchId':'b','sequence':[{'track':RAW}]}, {}, {}, {},
            {'radioSessionId':'track-session','batchId':'b2','sequence':[{'track':dict(RAW,id='13')}]}, {}]
        app.request('wave',trackId='12',title='Original seed')
        self.assertEqual(app.api.call.call_args_list[0].kwargs['json_body']['seeds'],['track:12'])
        self.assertEqual(app.state['waveKind'],'track')
        self.assertEqual(app.state['waveId'],'12')
        app.request('transport',action='next')
        self.assertEqual(app.state['id'],'13')
        self.assertEqual(app.state['waveTitle'],'Original seed')
        self.assertEqual(app.state['waveKind'],'track')
        app.request('play',id='13')
        self.assertFalse(app.state['wave'])
        self.assertEqual(app.state['waveKind'],'')
        self.assertEqual(app.state['waveTitle'],'')

    def test_playlist_wave_uses_playlist_seed_and_session_feedback(self):
        app = player()
        app.api.call.side_effect = [
            {'radioSessionId': 'playlist-session', 'batchId': 'b', 'sequence': [{'track': RAW}]}, {}, {}]
        app.request('wave', id='99:1000')
        self.assertEqual(app.api.call.call_args_list[0].kwargs['json_body']['seeds'], ['playlist:99_1000'])
        self.assertEqual(app.session, 'playlist-session')
        self.assertTrue(app.state['wave'])
        self.assertEqual(app.state['waveKind'],'playlist')
        self.assertEqual(app.state['waveId'],'99:1000')


class APITests(unittest.TestCase):
    def response(self, value):
        return io.BytesIO(json.dumps({'result': value}).encode())

    def test_oauth_header_and_json_wave_request(self):
        with patch('yandex_api.urlopen', return_value=self.response({'ok': True})) as open_url:
            API('token').call('rotor/session/new', json_body={'seeds': ['user:onyourwave']})
        request = open_url.call_args.args[0]
        self.assertEqual(request.get_header('Authorization'), 'OAuth token')
        self.assertEqual(request.get_header('Content-type'), 'application/json')
        self.assertEqual(json.loads(request.data), {'seeds': ['user:onyourwave']})
        self.assertEqual(request.full_url, 'https://api.music.yandex.net/rotor/session/new')

    def test_stream_signature_and_no_oauth_on_media_request(self):
        api = API('private-token')
        api.call = Mock(return_value=[{'codec': 'mp3', 'bitrateInKbps': 320,
                                      'downloadInfoUrl': 'https://storage.yandex.net/info'}])
        xml = b'<download-info><host>cdn.yandex.net</host><path>/file</path><ts>123</ts><s>salt</s></download-info>'
        with patch('yandex_api.urlopen', return_value=io.BytesIO(xml)) as open_url:
            url = api.stream('12')
        import hashlib
        signature = hashlib.md5(b'XGRlBW9FXlekgbPrRHuSiAfilesalt').hexdigest()
        self.assertEqual(url, 'https://cdn.yandex.net/get-mp3/' + signature + '/123/file')
        self.assertEqual(open_url.call_args.args[0], 'https://storage.yandex.net/info')
        self.assertNotIn('private-token', url)

    def test_untrusted_urls_and_redirects_rejected(self):
        for url in ['http://cdn.yandex.net/a', 'https://yandex.net.evil.org/a',
                    'https://user:password@cdn.yandex.net/a', 'file:///etc/passwd']:
            with self.subTest(url=url), self.assertRaises(YandexError):
                safe_url(url)
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.org'))

    def test_preview_is_not_playable(self):
        api = API('token')
        api.call = Mock(return_value=[{'codec': 'mp3', 'preview': True}])
        with self.assertRaisesRegex(YandexError, 'full-length'):
            api.stream('12')

    def test_auth_error_is_actionable_without_token(self):
        with patch('yandex_api.urlopen', side_effect=HTTPError('https://api.music.yandex.net', 401, 'bad', {}, None)):
            with self.assertRaisesRegex(YandexError, 'expired or invalid') as error:
                API('private-token').call('account/status')
        self.assertNotIn('private-token', str(error.exception))

    def test_token_is_passed_on_stdin_only(self):
        with patch('yandex_api.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='')) as run:
            token_store('private-token')
        self.assertNotIn('private-token', run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs['input'], 'private-token')

    def test_track_normalization(self):
        value = track({'track': RAW})
        self.assertEqual(value['duration'], 120)
        self.assertEqual(value['artistId'], '7')
        self.assertEqual(value['image'], 'https://avatars.yandex.net/400x400')


if __name__ == '__main__':
    unittest.main()
