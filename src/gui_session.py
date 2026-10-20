"""Forward only display-session variables to independent systemd applications."""
import os

GUI_VARIABLES = (
    'DISPLAY', 'XAUTHORITY', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR',
    'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME',
    'DBUS_SESSION_BUS_ADDRESS', 'XDG_CURRENT_DESKTOP', 'XDG_SESSION_DESKTOP',
    'XDG_SESSION_TYPE', 'DESKTOP_SESSION', 'KDE_FULL_SESSION',
    'KDE_SESSION_VERSION', 'GDK_BACKEND', 'QT_QPA_PLATFORM',
)


def systemd_environment(environ=None):
    environ = os.environ if environ is None else environ
    return ['--setenv='+name+'='+str(environ[name]) for name in GUI_VARIABLES
            if name in environ and not any(character in str(environ[name]) for character in ('\0', '\n', '\r'))]
