"""Real X11 pointer regression: desktop-window movement and button clicks.

Run under xvfb-run with xdotool; no window-manager move handling is needed.
"""
import os,sys,subprocess,time
from pathlib import Path
os.environ['GDK_BACKEND']='x11'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,Gdk
from window_drag import WindowDrag
w=Gtk.Window(title='Ember drag fixture');w.set_decorated(False);w.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
w.move(100,100);w.set_default_size(360,260)
b=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=35);w.add(b)
l=Gtk.Label(label='Drag this text');l.set_margin_top(24);b.pack_start(l,False,False,0)
bt=Gtk.Button(label='Click or drag button');b.pack_start(bt,False,False,0)
clicks=[];bt.connect('clicked',lambda *_:clicks.append(1))
saved=[]
d=WindowDrag(w,lambda:saved.append(tuple(w.get_position())));w.show_all()
def pump(s):
 t=time.monotonic()+s
 while time.monotonic()<t:
  for _ in range(8):
   if Gtk.events_pending():Gtk.main_iteration_do(False)
  time.sleep(.002)
def command(args):
 p=subprocess.Popen(['xdotool',*args])
 while p.poll() is None:pump(.01)
 assert p.returncode==0
 pump(.15)
pump(.2)
for item in (l,bt):
 old=tuple(w.get_position());pos=item.translate_coordinates(w,item.get_allocated_width()//2,item.get_allocated_height()//2)
 x,y=old[0]+pos[0],old[1]+pos[1]
 command(['mousemove',str(x),str(y),'mousedown','1','sleep','.1','mousemove',str(x+40),str(y+25),'sleep','.1','mousemove',str(x+90),str(y+55),'sleep','.1','mouseup','1'])
 new=tuple(w.get_position());print(type(item).__name__,old,new,'gesture',d.start,d.moving,'clicks',clicks,flush=True)
 assert new==(old[0]+90,old[1]+55),(old,new)
assert not clicks
assert len(saved)==2, saved
pos=bt.translate_coordinates(w,bt.get_allocated_width()//2,bt.get_allocated_height()//2);old=tuple(w.get_position())
command(['mousemove',str(old[0]+pos[0]),str(old[1]+pos[1]),'click','1'])
assert clicks==[1],clicks
w.destroy();print('PASS native pointer movement and click preservation')
