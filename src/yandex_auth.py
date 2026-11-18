"""Yandex Music device-code OAuth. Passwords are entered only at ya.ru/device."""
import json
import socket
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request
from yandex_api import YandexError, urlopen

# Public Music Android client credentials, also used by yamusic-rs.
CLIENT_ID = '23cabbbdc6cd418abb4b39c32c41195d'
CLIENT_SECRET = '53bc75238f0c4d08a118e51fe9203300'
DEVICE_URL = 'https://ya.ru/device'


def post(path, fields):
    request = Request('https://oauth.yandex.ru/' + path,
                      data=urlencode(fields).encode(),
                      headers={'Content-Type': 'application/x-www-form-urlencoded'})
    try:
        try:
            response = urlopen(request, timeout=15)
        except HTTPError as error:
            # OAuth pending/denied responses use HTTP 400, with a JSON body.
            if error.code != 400:
                error.close()
                raise YandexError('Yandex sign-in request failed.') from None
            response = error
        with response:
            value = json.loads(response.read(65536))
        if not isinstance(value, dict):
            raise ValueError('Invalid OAuth response')
        return value
    except (URLError, OSError, ValueError):
        raise YandexError('Could not reach Yandex sign-in. Check your connection and retry.') from None


def authorize(cancel, on_code):
    """Run off the UI thread; return a token or None on cancellation."""
    result = post('device/code', {'client_id': CLIENT_ID, 'device_id': uuid.uuid4().hex,
                                  'device_name': 'Emberbox (' + socket.gethostname() + ')'})
    device = result.get('device_code')
    code = result.get('user_code')
    if not isinstance(device, str) or not device or not isinstance(code, str) or not code:
        raise YandexError('Yandex did not issue a sign-in code. Please retry.')
    try:
        interval = max(1, int(result.get('interval', 5)))
        lifetime = max(1, int(result.get('expires_in', 300)))
    except (TypeError, ValueError):
        raise YandexError('Invalid Yandex sign-in response.') from None
    deadline = time.monotonic() + lifetime
    if cancel.is_set():
        return None
    on_code(code)
    while time.monotonic() < deadline:
        if cancel.wait(min(interval, max(0, deadline - time.monotonic()))):
            return None
        if time.monotonic() >= deadline:
            break
        value = post('token', {'grant_type': 'device_code', 'code': device,
                              'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET})
        if cancel.is_set():
            return None
        token = value.get('access_token')
        if isinstance(token, str) and token:
            return token
        error = value.get('error')
        if error == 'slow_down':
            interval += 5
        elif error != 'authorization_pending':
            messages = {'access_denied': 'Yandex sign-in was declined. Please retry.',
                        'expired_token': 'The sign-in code expired. Please retry.'}
            raise YandexError(messages.get(error, 'Yandex sign-in failed. Please retry.'))
    raise YandexError('The sign-in code expired. Please retry.')
