"""Optional integration test, only inside an isolated KWin/XWayland session.

Requires python-xlib for inspecting this test display and injecting test input.
Never run against the user's desktop: an explicit private-session marker and
temporary runtime directory are required. No music accounts or audio are used.
"""
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

if os.environ.get('EMBERBOX_ISOLATED_KWIN_TEST') != '1':
    raise SystemExit('Run only in an isolated KWin test session')
runtime = Path(os.environ.get('XDG_RUNTIME_DIR', ''))
if not str(runtime).startswith('/tmp/emberbox-kwin-check/'):
    raise SystemExit('A private test runtime directory is required')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkX11', '3.0')
from gi.repository import Gdk, GdkPixbuf, GdkX11, Gio, GLib, Gtk
from Xlib import X, XK, display
from Xlib.ext import xtest
import widget


def settle(seconds=.25):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        GLib.MainContext.default().iteration(False)
        time.sleep(.002)


class DummySound:
    def __init__(self, changed):
        self.changed=changed;self.available=False;self.volume=.6;self.muted=False
    def refresh(self, _target): pass
    def set_volume(self, _value): pass
    def toggle_mute(self): pass
    def close(self): pass


class DummyMonitor:
    def __init__(self, *_args): pass
    def poll(self): pass
    def close(self): pass


class DummyWeb:
    native=True
    def __init__(self, *_args):
        self.state={};self.enabled=False;self.connected=True;self.pid=0;self.error=''
    def set_enabled(self, enabled): self.enabled=enabled
    def action(self, *_args, **_kwargs): pass
    def ensure_started(self): pass
    def request(self, *_args, **_kwargs): return {'items':[], 'tracks':[], 'next':None}
    def close(self): pass


widget.SpotifyVolume=DummySound
widget.Monitor=DummyMonitor
widget.AppleWeb=widget.YandexWeb=DummyWeb
widget.SpotifyAudioMeter.start=lambda *_args:None
widget.Artwork.load=lambda _art,image,_url,size,*_args,**_kwargs:image.set_size_request(size,size)
widget.STATE=runtime/'window.json'
widget.STATE.write_text(json.dumps({'x':80,'y':80,'source':'spotify','compact':False}))
bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
reports=[]
interface=Gio.DBusNodeInfo.new_for_xml('''<node><interface name="org.emberbox.WindowTest">
<method name="Report"><arg type="s" direction="in"/></method></interface></node>''').interfaces[0]
bus.call_sync('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','RequestName',
              GLib.Variant('(su)',('org.emberbox.WindowTest',0)),None,Gio.DBusCallFlags.NONE,2000,None)


def report(_connection,_sender,_path,_interface,_method,parameters,invocation):
    reports.append(json.loads(parameters.unpack()[0]))
    invocation.return_value(None)


registration=bus.register_object('/Probe',interface,report,None,None)


def snapshot():
    index=len(reports)
    plugin='emberbox-window-probe-'+str(index)
    script=runtime/(plugin+'.js')
    script.write_text('''var rows=workspace.windowList().map(function(w) {
      return {caption:w.caption,normal:w.normalWindow,desktop:w.desktopWindow,
      below:w.keepBelow,layer:w.layer,allDesktops:w.onAllDesktops,active:w.active,
      skipTaskbar:w.skipTaskbar,skipPager:w.skipPager};});
      callDBus("org.emberbox.WindowTest","/Probe","org.emberbox.WindowTest","Report",JSON.stringify(rows));''')
    result=bus.call_sync('org.kde.KWin','/Scripting','org.kde.kwin.Scripting','loadScript',
        GLib.Variant('(ss)',(str(script),plugin)),None,Gio.DBusCallFlags.NONE,2000,None)
    identifier=result.unpack()[0]
    bus.call_sync('org.kde.KWin','/Scripting/Script'+str(identifier),'org.kde.kwin.Script','run',
        None,None,Gio.DBusCallFlags.NONE,2000,None)
    deadline=time.monotonic()+3
    while len(reports)==index and time.monotonic()<deadline:settle(.02)
    assert len(reports)>index,'KWin did not report managed windows'
    return reports[-1]


def click(child):
    point=child.translate_coordinates(app.window,0,0)
    position=app.window.get_position()
    x=position.root_x+point[0]+child.get_allocated_width()//2
    y=position.root_y+point[1]+child.get_allocated_height()//2
    xtest.fake_input(input_server,X.MotionNotify,x=x,y=y)
    input_server.sync();settle(.3)
    xtest.fake_input(input_server,X.ButtonPress,1)
    input_server.sync();settle(.06)
    xtest.fake_input(input_server,X.ButtonRelease,1)
    input_server.sync();settle(.3)


wallpaper=Gtk.Window(title='Emberbox synthetic desktop')
wallpaper.set_name('emberbox-test-wallpaper')
wallpaper.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
wallpaper.set_decorated(False)
wallpaper.move(0,0);wallpaper.set_default_size(1280,800)
wallpaper_css=Gtk.CssProvider()
wallpaper_css.load_from_data(b'#emberbox-test-wallpaper { background-color: #6b8e23; background-image: none; }')
wallpaper.get_style_context().add_provider(wallpaper_css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+100)
wallpaper.show_all()
app=widget.Widget()
xserver=display.Display()
input_server=display.Display(os.environ.get('EMBERBOX_KWIN_OUTER_DISPLAY'))
try:
    settle(1)
    assert app.desktop_mode=='normal'
    xid=app.window.get_window().get_xid()
    native=xserver.create_resource_object('window',xid)
    assert native.get_wm_class()==('emberbox-audio','EmberboxAudio')
    assert native.get_geometry().depth==32,'Widget needs its RGBA visual'
    row=next(row for row in snapshot() if row['caption']=='Emberbox Audio')
    assert row['normal'] and not row['desktop'] and row['below'] and row['allDesktops'],row
    assert row['skipTaskbar'] and row['skipPager']
    assert not row['active'],'Startup must not steal keyboard focus'
    initial_layer=row['layer']
    # Read the nested compositor's host output, not the uncomposited XWayland
    # client buffer. Green must show through the widget's rounded corner.
    position=app.window.get_position()
    root=input_server.screen().root
    def pixel(x,y):
        raw=root.get_image(x,y,1,1,X.ZPixmap,0xffffffff).data
        return tuple(raw[:3][::-1])
    corner=pixel(position.root_x+1,position.root_y+1)
    surface=pixel(position.root_x+200,position.root_y+4)
    assert all(abs(actual-expected)<=3 for actual,expected in zip(corner,(107,142,35))),corner
    assert surface!=corner and max(surface)<100,surface
    click(app.settings_button)
    assert app.settings.popover.get_visible(),'Settings did not receive the real pointer click'
    app.settings.popover.popdown();settle()
    app.select_source('youtube');settle()
    entry=app.youtube_panel.entry
    click(entry)
    keycode=input_server.keysym_to_keycode(XK.string_to_keysym('a'))
    xtest.fake_input(input_server,X.KeyPress,keycode);xtest.fake_input(input_server,X.KeyRelease,keycode)
    input_server.sync();settle()
    assert entry.get_text()=='a','KWin did not focus the search entry for keyboard input'
    before=app.window.get_position()
    point=app.cover.translate_coordinates(app.window,30,30)
    start_x,start_y=before.root_x+point[0],before.root_y+point[1]
    xtest.fake_input(input_server,X.MotionNotify,x=start_x,y=start_y)
    input_server.sync();settle(.1)
    xtest.fake_input(input_server,X.ButtonPress,1)
    input_server.sync();settle(.1)
    xtest.fake_input(input_server,X.MotionNotify,x=start_x+100,y=start_y+60)
    input_server.sync();settle(.2)
    xtest.fake_input(input_server,X.ButtonRelease,1)
    input_server.sync();settle(.2)
    after=app.window.get_position()
    assert after!=before,'KWin rejected desktop-widget movement'
    app.toggle_compact(None);settle()
    saved=(app.window.get_position(),app.window.get_size(),app.compact,app.expanded)
    app.show_fullscreen();settle(.6)
    stage=app.fullscreen
    row=next(row for row in snapshot() if row['caption']==stage.window.get_title())
    assert row['normal'] and not row['below'] and row['active'] and not row['allDesktops']
    assert row['layer']>initial_layer,'Listening room stayed on the desktop layer'
    stage.on_key(stage.window,SimpleNamespace(keyval=Gdk.KEY_Escape));settle()
    assert not stage.visible
    assert saved==(app.window.get_position(),app.window.get_size(),app.compact,app.expanded)
    print('PASS isolated KWin/XWayland: NORMAL/Below layer, composited rounded alpha, stable WM_CLASS, no startup focus steal, pointer settings, keyboard search, drag, fullscreen and restore',flush=True)
finally:
    bus.unregister_object(registration)
    app.close_resources()
    xserver.close()
    input_server.close()
    wallpaper.destroy()
