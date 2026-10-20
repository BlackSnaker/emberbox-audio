"""Desktop placement shared by GTK/X11 and Plasma's XWayland session.

KWin makes DESKTOP surfaces opaque and treats them as the wallpaper layer.
An ordinary, below-applications window preserves our alpha and input handling.
Other desktops retain the original desktop-surface mode.
"""
import os
import re
from collections import namedtuple

Area = namedtuple('Area', 'x y width height')


def desktop_mode(environ=None, wm_name=''):
    environ = os.environ if environ is None else environ
    override = environ.get('EMBERBOX_DESKTOP_MODE', '').strip().casefold()
    if override in ('normal', 'desktop'):
        return override
    names = re.split(r'[:;\s]+', ' '.join(str(environ.get(key, '')) for key in (
        'XDG_CURRENT_DESKTOP', 'XDG_SESSION_DESKTOP', 'DESKTOP_SESSION')).casefold())
    kde = any(name in ('kde', 'plasma', 'plasmawayland', 'plasma-wayland', 'plasmax11', 'plasma-x11')
              for name in names)
    return 'normal' if kde or wm_name.casefold().startswith('kwin') else 'desktop'


def configure(window):
    from gi.repository import Gdk
    wm_name = ''
    try:
        from gi.repository import GdkX11
        screen = window.get_screen()
        if isinstance(screen, GdkX11.X11Screen):
            wm_name = screen.get_window_manager_name() or ''
    except (ImportError, AttributeError, TypeError):
        pass
    mode = desktop_mode(wm_name=wm_name)
    window.set_wmclass('emberbox-audio', 'EmberboxAudio')
    window.set_role('desktop-widget')
    window.set_type_hint(Gdk.WindowTypeHint.NORMAL if mode == 'normal' else Gdk.WindowTypeHint.DESKTOP)
    window.set_keep_below(True)
    window.set_skip_taskbar_hint(True)
    window.set_skip_pager_hint(True)
    window.set_accept_focus(True)
    window.set_focus_on_map(False)
    window.stick()
    return mode


def usable_area(monitor):
    """Intersect EWMH work area with this monitor, including negative origins."""
    geometry = monitor.get_geometry()
    try:
        work = monitor.get_workarea()
    except (AttributeError, TypeError):
        work = geometry
    left, top = max(geometry.x, work.x), max(geometry.y, work.y)
    right = min(geometry.x+geometry.width, work.x+work.width)
    bottom = min(geometry.y+geometry.height, work.y+work.height)
    if right <= left or bottom <= top:
        return Area(geometry.x, geometry.y, geometry.width, geometry.height)
    return Area(left, top, right-left, bottom-top)


def clamp_position(x, y, width, height, area, margin=10):
    # Oversized drawers keep their top/left accessible rather than receiving a
    # negative upper bound and moving every configure-event.
    spare_x, spare_y = max(0, area.width-width), max(0, area.height-height)
    inset_x, inset_y = min(margin, spare_x//2), min(margin, spare_y//2)
    return (max(area.x+inset_x, min(x, area.x+spare_x-inset_x)),
            max(area.y+inset_y, min(y, area.y+spare_y-inset_y)))


def monitor_for(window):
    display = window.get_display()
    x, y = window.get_position()
    width, height = window.get_size()
    return (display.get_monitor_at_point(x+width//2, y+min(40, height//2)) or
            display.get_primary_monitor() or
            (display.get_monitor(0) if display.get_n_monitors() else None))
