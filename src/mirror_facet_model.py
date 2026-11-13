"""Small, looping mirror-scale geometry for the listening room's side walls.

No GTK objects or pixels are made here. A renderer can paint the convex quads
at its own frame rate and share the theme's existing animation clock.
"""
import math


PERIOD = 24.0
_COLUMNS = 32
_ROWS = 18
_EDGE_COLUMNS = 7


def _cells():
    for row in range(_ROWS):
        v = (row + .5) / _ROWS
        vertical_fade = .25 + .75 * math.sin(math.pi * v) ** .75
        for side in (0, 1):
            for edge_column in range(_EDGE_COLUMNS):
                column = edge_column if side == 0 else _COLUMNS - 1 - edge_column
                u = (column + .5) / _COLUMNS
                edge_fade = (1 - min(u, 1 - u) / .24) ** 1.15
                # Adjacent cells follow one wave; small fixed offsets avoid
                # making either wall look like a single rigid sheet.
                wave = row * .27 + edge_column * .22 + side * .85
                yield u, v, wave, edge_fade * vertical_fade


_CELLS = tuple(_cells())


def facets(age, width, height):
    """Return 252 ``(four_points, shade, alpha)`` tuples, or [] for no area.

    Coordinates are logical pixels. The middle 52% stays clear even while
    scales turn, shear and drift. ``shade`` and ``alpha`` are in [0, 1].
    Every motion repeats after :data:`PERIOD`; a nonfinite age means rest.
    """
    width, height = float(width), float(height)
    if not math.isfinite(width) or not math.isfinite(height) or width <= 0 or height <= 0:
        return []
    age = float(age)
    phase = (age % PERIOD) * math.tau / PERIOD if math.isfinite(age) else 0.
    motion_scale = min(width / 1920., height / 1080.)
    half_width = width / _COLUMNS * .465
    # Keep scales readable and safely in their side bands in narrow windows.
    half_height = min(height / _ROWS, width / _COLUMNS * 1.55) * .46
    camera_distance = 6 * max(half_width, half_height)
    corners = ((-half_width, -half_height), (half_width, -half_height),
               (half_width, half_height), (-half_width, half_height))
    result = []
    for u, v, offset, fade in _CELLS:
        wave = phase + offset
        sway, turn = math.sin(wave), math.cos(wave + .45)
        tilt_x = .40 * math.sin(wave - .8)
        tilt_y = .55 * turn
        sx, cx = math.sin(tilt_x), math.cos(tilt_x)
        sy, cy = math.sin(tilt_y), math.cos(tilt_y)
        angle = math.radians(4.7) * sway + math.radians(.6) * math.sin(phase - offset * .45)
        sine, cosine = math.sin(angle), math.cos(angle)
        shear = .035 * math.sin(wave - .4)
        local = []
        for x, y in corners:
            # A tilted plane under perspective stays a convex quadrilateral.
            px = cy * x + sy * sx * y
            py = cx * y
            depth = -sy * x + cy * sx * y
            perspective = 1 / (1 + depth / camera_distance)
            px, py = (px + shear * py) * perspective, py * perspective
            local.append((px * cosine - py * sine, px * sine + py * cosine))
        # Perspective shifts a quad's arithmetic centroid. Recenter it so the
        # wall scales float by less than three pixels at 1920 x 1080.
        local_x = sum(point[0] for point in local) * .25
        local_y = sum(point[1] for point in local) * .25
        centre_x = width * u + motion_scale * (1.8 * sway + .4 * math.sin(phase + offset * .4))
        centre_y = height * v + motion_scale * (1.35 * math.cos(wave - .3) + .35 * math.sin(phase - offset * .3))
        points = tuple((centre_x + x - local_x, centre_y + y - local_y) for x, y in local)
        # A broad reflected wash follows the physical tilt without blinking.
        shade = .45 + .15 * math.sin(wave + .65) + .10 * math.cos(phase - offset * .3)
        alpha = fade * (.35 + .07 * math.sin(wave + .2))
        result.append((points, shade, alpha))
    return result
