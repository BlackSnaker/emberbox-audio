"""Exercise real D-Bus discovery and command routing with two isolated players."""
import sys
from pathlib import Path
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from gi.repository import Gio,GLib
import control
from sources import Monitor,choose_session

connection=control.bus()
xml='''<node><interface name="org.freedesktop.DBus.Properties">
<method name="GetAll"><arg type="s" direction="in"/><arg type="a{sv}" direction="out"/></method>
</interface><interface name="org.mpris.MediaPlayer2.Player">
<method name="PlayPause"/><method name="Pause"/><method name="Next"/>
</interface></node>'''
info=Gio.DBusNodeInfo.new_for_xml(xml)
calls=[];exports=[];owners=[];connections=[]
for suffix,title in [('spotify','Spotify'),('firefox.instance42','Firefox')]:
    # Each real player has its own connection; shared bus_get_sync would
    # collapse both exported object paths into the same service instance.
    peer=Gio.DBusConnection.new_for_address_sync(
        __import__('os').environ['DBUS_SESSION_BUS_ADDRESS'],
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT|Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,None,None)
    connections.append(peer)
    def handler(conn,sender,path,iface,method,args,invocation,label=title):
        if method=='GetAll':
            interface=args.unpack()[0]
            if interface=='org.mpris.MediaPlayer2':
                values={'Identity':GLib.Variant('s',label),'DesktopEntry':GLib.Variant('s',label.lower())}
            else:
                values={'PlaybackStatus':GLib.Variant('s','Paused'),
                        'Metadata':GLib.Variant('a{sv}',{'xesam:title':GLib.Variant('s',label+' fixture')})}
            invocation.return_value(GLib.Variant('(a{sv})',(values,)))
        else:
            calls.append((label,method));invocation.return_value(None)
    for interface in info.interfaces:
        exports.append((peer,peer.register_object(control.PATH,interface,handler,None,None)))
    owners.append(Gio.bus_own_name_on_connection(peer,'org.mpris.MediaPlayer2.'+suffix,Gio.BusNameOwnerFlags.NONE,None,None))

def until(predicate,timeout=4):
    end=time.monotonic()+timeout
    while not predicate() and time.monotonic()<end:
        while GLib.MainContext.default().pending(): GLib.MainContext.default().iteration(False)
        time.sleep(.005)
    assert predicate(),'D-Bus fixture timed out'

results=[]
monitor=Monitor(connection,lambda sessions:results.append(sessions))
until(lambda: all(peer.get_unique_name() for peer in connections))
monitor.poll()
until(lambda:bool(results))
sessions=results[-1]
spotify=choose_session(sessions,'spotify')
apple=choose_session(sessions,'apple-music','firefox')
assert spotify.identity=='Spotify' and apple.identity=='Firefox'
monitor.call(apple,'PlayPause');monitor.call(spotify,'Next')
until(lambda:len(calls)==2)
assert calls==[('Firefox','PlayPause'),('Spotify','Next')],calls
monitor.close()
for peer,export in exports:peer.unregister_object(export)
for owner in owners:Gio.bus_unown_name(owner)
for peer in connections:peer.close_sync(None)
print('PASS real MPRIS discovery and source-specific command routing')
