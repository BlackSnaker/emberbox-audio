"""A cold lamp cache must not hold the GTK loop or the first visible window."""
from pathlib import Path
import sys,tempfile,threading,time
from unittest.mock import patch
import gi
gi.require_version('Gtk','3.0');gi.require_version('GdkPixbuf','2.0')
from gi.repository import GLib,Gtk
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import nixie_spectrum as lamps

def spin(until,limit):
 end=time.monotonic()+limit
 while not until() and time.monotonic()<end:
  while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
  time.sleep(.002)
 assert until(),'GTK fixture timed out'

with tempfile.TemporaryDirectory(prefix='ember-cold-lamps-') as folder:
 lamps.CACHE_DIR=Path(folder);release=threading.Event();real=lamps.frames
 def deferred():
  assert release.wait(4),'Fixture never released lamp preparation'
  return real()
 window=Gtk.Window();heartbeats=[]
 with patch.object(lamps,'frames',side_effect=deferred):
  started=time.perf_counter();view=lamps.NixieSpectrum();elapsed=time.perf_counter()-started
  window.add(view);window.show_all()
  timer=GLib.timeout_add(10,lambda:(heartbeats.append(time.monotonic()),True)[1])
  try:
   spin(lambda:len(heartbeats)>=8,2)
   assert window.get_mapped() and not view.frames_ready and not lamps._FRAME_JOB.done()
   view.set_compact(True);view.set_levels([.6]*9)
   release.set();spin(lambda:view.frames_ready,8)
   assert view.compact and view.frames is view.mini_frames and len(view.full_frames)==384
   assert view.indices==[round(.6*383)]*9
   print('PASS cold lamp cache: first widget '+str(round(elapsed*1000,1))+'ms; GTK heartbeats before preparation; full 384 frames delivered in Mini')
  finally:release.set();GLib.source_remove(timer);window.destroy()
