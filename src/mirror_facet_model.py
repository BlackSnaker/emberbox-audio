"""Panoramic mirror-room inspection geometry, moving only left to right.

The live renderer translates one repeating texture. No tile geometry is built
on its frame clock, and horizontal wrapping never changes the room's height.
"""
import math

PERIOD = 24.0
DRIFT_PERIOD = PERIOD * 3
COLUMNS, ROWS = 32, 18


def offset(age):
    age = float(age)
    return (age / DRIFT_PERIOD) % 1 if math.isfinite(age) else 0.


def facets(age, width, height):
    """Return 576 convex panes; the panorama wraps seamlessly at each edge."""
    width, height = float(width), float(height)
    if not math.isfinite(width) or not math.isfinite(height) or width <= 0 or height <= 0:
        return []
    drift = offset(age)
    result = []
    for row in range(ROWS):
        top, bottom = (row + .025) / ROWS, (row + .975) / ROWS
        stagger = (row % 2) * .5
        for col in range(COLUMNS):
            centre = (col + .5 - stagger) / COLUMNS + drift
            centre = (centre + .5 / COLUMNS) % 1 - .5 / COLUMNS
            points = tuple((width * (centre + dx / COLUMNS - .21 * math.sin(v * math.tau) / COLUMNS), height * v)
                           for dx, v in ((-.478, top), (.478, top), (.478, bottom), (-.478, bottom)))
            reflection = (.5 + .5 * math.cos(col * math.tau / 8 + row * .72)) ** 3
            result.append((points, .2 + .7 * reflection, .4 + .12 * reflection))
    return result
