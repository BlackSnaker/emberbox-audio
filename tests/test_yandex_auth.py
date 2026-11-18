"""Device OAuth tests: no live account or browser is used."""
import io
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import yandex_auth as auth
from yandex_api import YandexError


class DeviceAuthTests(unittest.TestCase):
    def code(self):
        return {'device_code': 'private-device', 'user_code': 'ABCD-EFGH', 'expires_in': 300, 'interval': 1}

    def test_pending_slow_down_then_success(self):
        cancel = Mock()
        cancel.is_set.return_value = False
        cancel.wait.return_value = False
        show = Mock()
        with patch.object(auth, 'post', side_effect=[self.code(), {'error': 'authorization_pending'},
                                                    {'error': 'slow_down'}, {'access_token': 'private-token'}]) as post:
            self.assertEqual(auth.authorize(cancel, show), 'private-token')
        show.assert_called_once_with('ABCD-EFGH')
        self.assertEqual([c.args[0] for c in cancel.wait.call_args_list], [1, 1, 6])
        self.assertEqual(post.call_args.args[1]['grant_type'], 'device_code')
        self.assertEqual(post.call_args.args[1]['code'], 'private-device')
        self.assertEqual(post.call_args_list[0].args[0], 'device/code')

    def test_cancel_never_requests_token(self):
        cancel = threading.Event()
        def show(_code):
            cancel.set()
        with patch.object(auth, 'post', return_value=self.code()) as post:
            self.assertIsNone(auth.authorize(cancel, show))
        post.assert_called_once()

    def test_denied_or_expired_is_actionable(self):
        cancel = Mock()
        cancel.is_set.return_value = False
        cancel.wait.return_value = False
        for error, message in [('access_denied', 'declined'), ('expired_token', 'expired')]:
            with self.subTest(error=error), patch.object(auth, 'post', side_effect=[self.code(), {'error': error}]), \
                 self.assertRaisesRegex(YandexError, message):
                auth.authorize(cancel, Mock())

    def test_local_expiry_does_not_poll_after_deadline(self):
        cancel = Mock()
        cancel.is_set.return_value = False
        cancel.wait.return_value = False
        with patch.object(auth, 'post', return_value=self.code()) as post, \
             patch.object(auth.time, 'monotonic', side_effect=[0, 301]), \
             self.assertRaisesRegex(YandexError, 'expired'):
            auth.authorize(cancel, Mock())
        post.assert_called_once()

    def test_http_400_pending_is_parsed(self):
        error = HTTPError('https://oauth.yandex.ru/token', 400, 'pending', {},
                          io.BytesIO(b'{"error":"authorization_pending"}'))
        with patch.object(auth, 'urlopen', side_effect=error):
            self.assertEqual(auth.post('token', {'code': 'private'}), {'error': 'authorization_pending'})

    def test_token_request_uses_fixed_https_host_and_form_body(self):
        with patch.object(auth, 'urlopen', return_value=io.BytesIO(b'{"access_token":"private"}')) as opened:
            auth.post('token', {'code': 'private-device'})
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, 'https://oauth.yandex.ru/token')
        self.assertEqual(request.data, b'code=private-device')
        self.assertNotIn('private-device', request.full_url)

    def test_server_error_description_is_not_exposed(self):
        with patch.object(auth, 'post', return_value={'error_description': 'secret-server-data'}), \
             self.assertRaises(YandexError) as caught:
            auth.authorize(threading.Event(), Mock())
        self.assertNotIn('secret-server-data', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
