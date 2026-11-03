"""The hidden desktop visual loop must stay asleep behind fullscreen playback."""
import sys,time,tempfile
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from frame_health import FrameHealth


class FrameSuspension(TestCase):
    def test_suspended_visuals_do_not_trigger_watchdog_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            health=FrameHealth.__new__(FrameHealth)
            health.closed=False;health.suspended=True;health.last_frame=time.monotonic()-60
            health.window=Mock();health.window.get_mapped.return_value=True
            health.obscured=False;health.recoveries=0;health.tick=0;health.frames=0;health.paints=0
            health.animate=lambda *_:True;health.path=Path(folder)/'health.json';health.request_frame=Mock()
            with patch('frame_health.Gtk.grab_get_current',return_value=None):health.check()
            health.window.add_tick_callback.assert_not_called();health.request_frame.assert_not_called()
            self.assertEqual(health.recoveries,0)

    def test_resume_restores_exactly_one_visual_clock(self):
        health=FrameHealth.__new__(FrameHealth);health.closed=False;health.suspended=False;health.tick=4
        health.window=Mock();health.window.add_tick_callback.return_value=7;health.request_frame=Mock()
        health.set_suspended(True);health.set_suspended(True)
        health.window.remove_tick_callback.assert_called_once_with(4);self.assertEqual(health.tick,0)
        health.set_suspended(False);health.set_suspended(False)
        health.window.add_tick_callback.assert_called_once();health.request_frame.assert_called_once()
        self.assertEqual(health.tick,7)
        health.closed=True;health.set_suspended(True)
        self.assertEqual(health.tick,7,'Closing must never restart clocks')

    def test_fullscreen_suspends_desktop_only_and_restores_it_on_exit(self):
        from fullscreen import FullscreenPlayer
        desktop=Mock();clock=Mock();stage=NS(host=NS(winter_surface=NS(snow=desktop),frame_health=clock))
        FullscreenPlayer.suspend_desktop_visuals(stage,True)
        desktop.set_suspended.assert_called_once_with(True);clock.set_suspended.assert_called_once_with(True)
        FullscreenPlayer.suspend_desktop_visuals(stage,False)
        self.assertEqual(desktop.set_suspended.call_args.args,(False,))
