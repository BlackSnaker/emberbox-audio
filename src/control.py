"""Small MPRIS helpers for the running Spotify desktop client."""
from gi.repository import Gio, GLib

PREFIX = 'org.mpris.MediaPlayer2.spotify'
PATH = '/org/mpris/MediaPlayer2'
PLAYER = 'org.mpris.MediaPlayer2.Player'


def bus():
    return Gio.bus_get_sync(Gio.BusType.SESSION, None)


def player_name(connection):
    result = connection.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                                  'org.freedesktop.DBus', 'ListNames', None,
                                  GLib.VariantType.new('(as)'), Gio.DBusCallFlags.NONE, 1000, None)
    return next((name for name in result.unpack()[0] if name.startswith(PREFIX)), None)


def property_value(connection, name, key):
    result = connection.call_sync(name, PATH, 'org.freedesktop.DBus.Properties', 'Get',
                                  GLib.Variant('(ss)', (PLAYER, key)),
                                  GLib.VariantType.new('(v)'), Gio.DBusCallFlags.NONE, 1000, None)
    return result.get_child_value(0).get_variant().unpack()
