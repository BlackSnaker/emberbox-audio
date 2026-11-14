"""Small, time-based optical responses; no clocks, capture or media processing."""
import hashlib
import json
import math
from itertools import islice


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def _unit(value):
    value = _finite(value)
    return min(1., max(0., value)) if value is not None else 0.


def _smooth(current, target, dt, seconds):
    return current + (target-current) * -math.expm1(-dt/seconds)


def _metadata(key):
    if not isinstance(key, (tuple, list)) or not key:
        return None
    for value in key:
        if value is None or isinstance(value, (str, int, bool)):
            continue
        if isinstance(value, float) and math.isfinite(value):
            continue
        return None
    return tuple(key)


def _character(key):
    payload = json.dumps(key, separators=(',', ':'), allow_nan=False).encode('ascii')
    digest = hashlib.blake2s(payload, digest_size=6).digest()
    return tuple(.2 + .6*int.from_bytes(digest[index:index+2], 'big')/65535
                 for index in (0, 2, 4))


def _bands(meter):
    values = getattr(meter, 'levels', ())
    if isinstance(values, (str, bytes)):
        return (0.,)*9
    try:
        values = tuple(_unit(value) for value in islice(iter(values), 9))
    except (TypeError, ValueError):
        return (0.,)*9
    return values + (0.,)*(9-len(values))


class Optics:
    """Pulse, energy, bass, air and a gently changing three-part song character."""

    def __init__(self):
        self._response = (0.,)*4
        self._character = (.5,)*3
        self._target = self._character
        self._key = None

    @property
    def values(self):
        return self._response + self._character

    def advance(self, dt, rhythm):
        dt = _finite(dt)
        if dt is None or dt <= 0:
            return self.values
        fresh = getattr(rhythm, 'fresh', False) is True
        targets = (0.,)*4
        if fresh:
            meter = getattr(rhythm, 'meter', None)
            timing = getattr(rhythm, 'timing', None)
            bpm = _finite(getattr(timing, 'bpm', None))
            pulse = _unit(getattr(timing, 'accent', 0.)) if bpm is not None and 80 <= bpm <= 180 else 0.
            bands = _bands(meter)
            targets = (pulse, _unit(getattr(meter, 'rms_level', 0.)),
                       sum(bands[:3])/3, sum(bands[6:])/3)
            key = _metadata(getattr(rhythm, 'key', None))
            if key is not None and key != self._key:
                self._key, self._target = key, _character(key)
            self._character = tuple(_smooth(current, target, dt, 3.5)
                                    for current, target in zip(self._character, self._target))
        responses = []
        for index, (current, target) in enumerate(zip(self._response, targets)):
            attack, release = (.10, .35) if index == 0 else (.55, 1.3)
            responses.append(_smooth(current, target, dt, attack if target > current else release))
        self._response = tuple(responses)
        return self.values
