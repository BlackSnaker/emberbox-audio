"""Small session-bus interface for showing an existing desktop widget."""
from gi.repository import Gio, GLib
from paths import APP_ID

NAME='org.emberbox.Widget.'+APP_ID.replace('-','_')
PATH='/org/emberbox/Widget'
INTERFACE='org.emberbox.Widget'
METHODS=('Show','Hide','Quit')
XML='<node><interface name="'+INTERFACE+'">'+''.join('<method name="'+name+'"/>' for name in METHODS)+'</interface></node>'


def send(method='Show'):
    if method not in METHODS:raise ValueError('Unknown widget action')
    try:
        connection=Gio.bus_get_sync(Gio.BusType.SESSION,None)
        connection.call_sync(NAME,PATH,INTERFACE,method,None,None,
                             Gio.DBusCallFlags.NO_AUTO_START,1500,None)
        return True
    except GLib.Error:
        return False


class WidgetControl:
    def __init__(self,show,hide,quit):
        self.connection=None;self.registration=0;self.owned=False
        self.actions=dict(zip(METHODS,(show,hide,quit)))
        try:
            self.connection=Gio.bus_get_sync(Gio.BusType.SESSION,None)
            result=self.connection.call_sync('org.freedesktop.DBus','/org/freedesktop/DBus',
                'org.freedesktop.DBus','RequestName',GLib.Variant('(su)',(NAME,4)),
                GLib.VariantType.new('(u)'),Gio.DBusCallFlags.NONE,1500,None)
            self.owned=result.unpack()[0] in (1,4)
            if self.owned:
                interface=Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0]
                self.registration=self.connection.register_object(PATH,interface,self._call,None,None)
        except GLib.Error:
            self.close()

    def _call(self,connection,sender,path,interface,method,parameters,invocation):
        # Reply before a Quit callback tears down the interface.
        invocation.return_value(None)
        callback=self.actions[method]
        GLib.idle_add(lambda: (callback(),False)[1])

    def close(self):
        if self.registration:
            self.connection.unregister_object(self.registration);self.registration=0
        if self.owned:
            try:
                self.connection.call_sync('org.freedesktop.DBus','/org/freedesktop/DBus',
                    'org.freedesktop.DBus','ReleaseName',GLib.Variant('(s)',(NAME,)),
                    None,Gio.DBusCallFlags.NONE,1000,None)
            except GLib.Error:pass
            self.owned=False
