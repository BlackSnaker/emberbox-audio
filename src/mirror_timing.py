"""Smooth a measured beat grid into the mirror wave's speed and soft accent.

The caller owns the clock and integrates wave age using the returned speed.
Changing tracks or acquiring a pulse never resets that continuous wave age.
"""
import math


def _finite(value):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _grid(grid):
    try:
        bpm = _finite(grid.get('bpm'))
        period = _finite(grid.get('period'))
        phase = _finite(grid.get('phase'))
        confidence = _finite(grid.get('confidence'))
    except AttributeError:
        return None
    if bpm is None or not 80 <= bpm <= 180:
        return None
    if period is None or period <= 0 or not math.isclose(period, 60 / bpm, rel_tol=.01, abs_tol=1e-8):
        return None
    if phase is None or confidence is None or not .72 <= confidence <= 1:
        return None
    return bpm, period, phase


def _smooth(current, target, dt, seconds):
    return current + (target - current) * -math.expm1(-dt / seconds)


class Timing:
    """Bounded, time-based smoothing with no timers or audio-device ownership."""

    def __init__(self):
        self.speed = .35
        self.bpm = None
        self.accent = 0.
        self.gain = 1.

    def advance(self, dt, grid, now, active=True, fresh=True):
        """Advance by seconds and return the wave's smooth playback speed.

        Confident 80–180 BPM grids give a 32-beat, 24-source-second wave.
        An active fresh source without a valid grid drifts gently; inactive
        or stale sources settle. Invalid time samples leave all state intact.
        """
        dt, now = _finite(dt), _finite(now)
        if dt is None or dt <= 0 or now is None:
            return self.speed
        moving = bool(active and fresh)
        measured = _grid(grid) if moving else None
        self.bpm = measured[0] if measured else None
        target_speed = self.bpm / 80 if measured else .35 if moving else 0.
        self.speed = _smooth(self.speed, target_speed, dt, 1.2)
        if measured:
            _, period, phase = measured
            # Reduce separately to avoid overflow for finite but extreme
            # clocks/phases. EnergyTap's phase uses this monotonic time base.
            elapsed = (now % period - phase % period) % period
            target_accent = math.exp(-elapsed / .10)
        else:
            target_accent = 0.
        envelope = .035 if target_accent > self.accent else .15
        self.accent = min(1., max(0., _smooth(self.accent, target_accent, dt, envelope)))
        target_gain = .92 + .16 * self.accent if measured else 1.
        self.gain = _smooth(self.gain, target_gain, dt, .15)
        return self.speed
