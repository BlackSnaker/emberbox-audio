"""Offline 1080p frame cadence with normal fullscreen meters and timer.

Run on a quiet 60 Hz reference display or an isolated Xvfb display. Uses only
original fixture media and playback stubs; never reads account or desktop audio.
"""
from pathlib import Path
import sys,time
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'src')]
import fullscreen_smoke as fixture
import fullscreen
from gi.repository import Gtk
settings=Gtk.Settings.get_default();settings.set_property('gtk-enable-animations',False)
with patch('urllib.request.urlopen',side_effect=AssertionError('No fixture network')),\
     patch.object(fullscreen,'LyricsClient',fixture.FixtureLyrics),\
     patch.object(fullscreen.Artwork,'load',fixture.image_load):
 host=fixture.FixtureHost();stage=fullscreen.FullscreenPlayer(host);host.fullscreen=stage
 try:
  stage.open();fixture.settle(.2);stage.window.unfullscreen();stage.window.resize(1920,1080);fixture.settle(.5)
  settings.set_property('gtk-enable-animations',True);stage.update();times=[];clock=stage.window.get_frame_clock()
  def presented(clock):
   if stage.cover_pause.tick and stage.cover_pause.age>.08:times.append(clock.get_frame_time())
  handler=clock.connect('after-paint',presented)
  host.playing=False;stage.update()
  deadline=time.monotonic()+5
  while not stage.cover_pause.tick and time.monotonic()<deadline:fixture.settle(.01)
  while stage.cover_pause.tick and time.monotonic()<deadline:fixture.settle(.01)
  clock.disconnect(handler)
  assert len(times)>20 and not stage.cover_pause.tick,(len(times),stage.cover_pause.tick)
  fps=(len(times)-1)*1e6/(times[-1]-times[0]);p95=float(np.percentile(np.diff(times)/1000,95))
  print('FULLSCREEN 1920x1080, normal meters/timer active, cover',stage.art_size,':',round(fps,2),'FPS, p95',round(p95,2),'ms')
  assert fps>=58.5 and p95<18.5,(fps,p95)
 finally:stage.close();host.window.destroy()
