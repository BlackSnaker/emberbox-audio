"""Real isolated D-Bus show/hide/quit routing; no media or desktop access."""
from pathlib import Path
import subprocess,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from gi.repository import GLib
from widget_control import WidgetControl
calls=[]
server=WidgetControl(lambda:calls.append('Show'),lambda:calls.append('Hide'),lambda:calls.append('Quit'))
assert server.owned
try:
    for index,action in enumerate(('Hide','Show','Show','Quit')):
        code='import sys;sys.path.insert(0,sys.argv[1]);from widget_control import send;sys.exit(0 if send(sys.argv[2]) else 1)'
        process=subprocess.Popen([sys.executable,'-B','-c',code,str(Path(__file__).resolve().parents[1]/'src'),action])
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and (process.poll() is None or len(calls)<index+1):
            while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
            time.sleep(.01)
        assert process.wait(timeout=1)==0
        while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
    assert calls==['Hide','Show','Show','Quit'],calls
finally:server.close()
print('PASS real D-Bus hide, repeat activation and close requests')
