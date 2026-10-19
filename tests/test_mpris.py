"""The real D-Bus contract, with fixture playback on a private session bus."""
from pathlib import Path
import sys
import threading
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from gi.repository import Gio,GLib
from ember_mpris import EmberMpris,NAME,PATH,ROOT,PLAYER


class MprisTests(unittest.TestCase):
    def test_identity_metadata_transport_seek_and_volume(self):
        bus = Gio.TestDBus.new(Gio.TestDBusFlags.NONE);bus.up()
        flags = Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT|Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION
        connection = Gio.DBusConnection.new_for_address_sync(bus.get_bus_address(),flags,None,None)
        client = Gio.DBusConnection.new_for_address_sync(bus.get_bus_address(),flags,None,None)
        actions,seeks,volumes,errors = [],[],[],[]
        service = EmberMpris(connection,lambda method,*args:actions.append((method,*args)),seeks.append,volumes.append)
        service.publish({'active':True,'source':'apple-music','id':'fixture','title':'Fixture song',
                         'artist':'Fixture artist','duration':180_000_000,'position':1_000_000,'playing':True,
                         'next':True,'previous':True,'volume':.6})
        loop = GLib.MainLoop()
        def check():
            try:
                def call(interface,method,args=None):
                    return client.call_sync(NAME,PATH,interface,method,args,None,Gio.DBusCallFlags.NONE,1500,None)
                for _ in range(40):
                    try:
                        identity = call('org.freedesktop.DBus.Properties','Get',GLib.Variant('(ss)',(ROOT,'Identity'))).unpack()[0]
                        break
                    except GLib.Error:time.sleep(.03)
                else:raise AssertionError('Ember service did not acquire its name')
                self.assertEqual(identity,'Ember')
                metadata = call('org.freedesktop.DBus.Properties','Get',GLib.Variant('(ss)',(PLAYER,'Metadata'))).unpack()[0]
                self.assertEqual(metadata['xesam:title'],'Fixture song')
                self.assertEqual(metadata['mpris:length'],180_000_000)
                call(PLAYER,'Next');call(PLAYER,'Pause')
                call(PLAYER,'OpenUri',GLib.Variant('(s)',('apple:songs:123',)))
                with self.assertRaises(GLib.Error):
                    call(PLAYER,'OpenUri',GLib.Variant('(s)',('file:///etc/passwd',)))
                call(PLAYER,'Seek',GLib.Variant('(x)',(1_000_000,)))
                call(PLAYER,'SetPosition',GLib.Variant('(ox)',('/org/emberbox/stale',20_000_000)))
                call(PLAYER,'SetPosition',GLib.Variant('(ox)',(metadata['mpris:trackid'],30_000_000)))
                call('org.freedesktop.DBus.Properties','Set',GLib.Variant('(ssv)',(PLAYER,'Volume',GLib.Variant('d',.35))))
                self.assertEqual(actions,[('Next',),('Pause',),('OpenUri','apple:songs:123')])
                self.assertEqual(seeks,[2.,30.])
                self.assertEqual(volumes,[.35])
            except Exception as error:errors.append(error)
            finally:GLib.idle_add(loop.quit)
        thread = threading.Thread(target=check,daemon=True);thread.start()
        timeout = GLib.timeout_add_seconds(8,lambda:(errors.append(AssertionError('D-Bus test timeout')),loop.quit(),False)[-1])
        try:
            loop.run();thread.join(timeout=2)
            self.assertFalse(errors,errors)
        finally:
            GLib.source_remove(timeout)
            service.close();client.close_sync(None);connection.close_sync(None);bus.down()
