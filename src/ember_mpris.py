"""Publish native playback as Ember in the desktop's standard media controls."""
import hashlib
from gi.repository import Gio,GLib

NAME = 'org.mpris.MediaPlayer2.emberbox_audio'
PATH = '/org/mpris/MediaPlayer2'
ROOT = 'org.mpris.MediaPlayer2'
PLAYER = ROOT+'.Player'
XML = '''<node>
<interface name="org.mpris.MediaPlayer2">
 <method name="Raise"/><method name="Quit"/>
 <property name="CanQuit" type="b" access="read"/>
 <property name="CanRaise" type="b" access="read"/>
 <property name="HasTrackList" type="b" access="read"/>
 <property name="Identity" type="s" access="read"/>
 <property name="DesktopEntry" type="s" access="read"/>
 <property name="SupportedUriSchemes" type="as" access="read"/>
 <property name="SupportedMimeTypes" type="as" access="read"/>
</interface>
<interface name="org.mpris.MediaPlayer2.Player">
 <method name="Next"/><method name="Previous"/><method name="Pause"/>
 <method name="PlayPause"/><method name="Stop"/><method name="Play"/>
 <method name="Seek"><arg type="x" direction="in"/></method>
 <method name="SetPosition"><arg type="o" direction="in"/><arg type="x" direction="in"/></method>
 <method name="OpenUri"><arg type="s" direction="in"/></method>
 <signal name="Seeked"><arg type="x"/></signal>
 <property name="PlaybackStatus" type="s" access="read"/>
 <property name="Rate" type="d" access="readwrite"/>
 <property name="Metadata" type="a{sv}" access="read"/>
 <property name="Volume" type="d" access="readwrite"/>
 <property name="Position" type="x" access="read"/>
 <property name="MinimumRate" type="d" access="read"/>
 <property name="MaximumRate" type="d" access="read"/>
 <property name="CanGoNext" type="b" access="read"/>
 <property name="CanGoPrevious" type="b" access="read"/>
 <property name="CanPlay" type="b" access="read"/>
 <property name="CanPause" type="b" access="read"/>
 <property name="CanSeek" type="b" access="read"/>
 <property name="CanControl" type="b" access="read"/>
</interface></node>'''


class EmberMpris:
    def __init__(self,connection,action,seek,volume):
        self.connection,self.action,self.seek,self.volume = connection,action,seek,volume
        self.state = {}
        self.owner = 0
        self.last = {}
        self.objects = [connection.register_object(PATH,interface,self._call,self._get,self._set)
                        for interface in Gio.DBusNodeInfo.new_for_xml(XML).interfaces]

    def properties(self,interface):
        if interface == ROOT:
            return {**{key:GLib.Variant('b',False) for key in ('CanQuit','CanRaise','HasTrackList')},
                    'Identity':GLib.Variant('s','Ember'),
                    'DesktopEntry':GLib.Variant('s','emberbox-audio-player'),
                    'SupportedUriSchemes':GLib.Variant('as',['apple']),'SupportedMimeTypes':GLib.Variant('as',[])}
        state = self.state
        active = bool(state.get('active') and state.get('title'))
        metadata = {}
        if active:
            ident = hashlib.sha256(str((state.get('source'),state.get('id'),state.get('title'))).encode()).hexdigest()[:24]
            metadata = {'mpris:trackid':GLib.Variant('o','/org/emberbox/track/'+ident),
                        'mpris:length':GLib.Variant('x',int(state.get('duration',0))),
                        'xesam:title':GLib.Variant('s',state.get('title','')),
                        'xesam:artist':GLib.Variant('as',[state.get('artist','')]),
                        'xesam:album':GLib.Variant('s',state.get('album',''))}
            if state.get('image'):
                metadata['mpris:artUrl'] = GLib.Variant('s',state['image'])
        return {'PlaybackStatus':GLib.Variant('s','Playing' if active and state.get('playing') else 'Paused' if active else 'Stopped'),
                'Metadata':GLib.Variant('a{sv}',metadata),
                'Rate':GLib.Variant('d',1.),'MinimumRate':GLib.Variant('d',1.),'MaximumRate':GLib.Variant('d',1.),
                'Volume':GLib.Variant('d',float(state.get('volume',1.))),
                'Position':GLib.Variant('x',max(0,int(state.get('position',0)))),
                **{key:GLib.Variant('b',bool(value)) for key,value in {
                    'CanGoNext':active and state.get('next'),'CanGoPrevious':active and state.get('previous'),
                    'CanPlay':active,'CanPause':active,'CanSeek':active and state.get('duration',0)>0,
                    'CanControl':True}.items()}}

    def publish(self,state):
        self.state = state
        active = bool(state.get('active'))
        if active and not self.owner:
            self.owner = Gio.bus_own_name_on_connection(self.connection,NAME,Gio.BusNameOwnerFlags.NONE,None,None)
            self.last = {}
        elif not active and self.owner:
            Gio.bus_unown_name(self.owner)
            self.owner = 0
        props = {key:value for key,value in self.properties(PLAYER).items() if key!='Position'}
        changed = {key:value for key,value in props.items() if value != self.last.get(key)}
        self.last = props
        if self.owner and changed:
            self.connection.emit_signal(None,PATH,'org.freedesktop.DBus.Properties','PropertiesChanged',
                                        GLib.Variant('(sa{sv}as)',(PLAYER,changed,[])))

    def _get(self,_connection,_sender,_path,interface,key):
        return self.properties(interface).get(key)

    def _set(self,_connection,_sender,_path,interface,key,value):
        if interface == PLAYER and key=='Volume':
            self.volume(max(0.,min(1.,value.unpack())))
            return True
        return interface == PLAYER and key=='Rate' and value.unpack()==1.

    def _call(self,_connection,_sender,_path,interface,method,params,invocation):
        if interface == ROOT:
            invocation.return_value(None)
            return
        if method == 'OpenUri':
            import re
            uri = params.unpack()[0]
            if self.state.get('source')=='apple-music' and re.fullmatch(r'apple:(songs|library-songs|library-albums|library-playlists):[\w.-]{1,200}',uri):
                self.action(method,uri)
                invocation.return_value(None)
            else:
                invocation.return_dbus_error('org.mpris.MediaPlayer2.Player.Error.NotSupported','Choose music inside Ember.')
            return
        if self.state.get('active'):
            values = params.unpack()
            if method in ('Seek','SetPosition'):
                metadata = self.properties(PLAYER)['Metadata'].unpack()
                if method=='SetPosition' and values[0] != metadata.get('mpris:trackid'):
                    invocation.return_value(None)
                    return
                position = self.state.get('position',0)+values[0] if method=='Seek' else values[1]
                position = max(0,min(self.state.get('duration',0),position))
                self.seek(position/1_000_000)
                self.connection.emit_signal(None,PATH,PLAYER,'Seeked',GLib.Variant('(x)',(int(position),)))
            else:
                self.action(method)
        invocation.return_value(None)

    def close(self):
        if self.owner:
            Gio.bus_unown_name(self.owner)
        for identifier in self.objects:
            self.connection.unregister_object(identifier)
