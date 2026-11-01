from pathlib import Path
import sys,time
from unittest import TestCase
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from apple_web import AppleWeb


class EngineStartup(TestCase):
    def app(self):
        a=AppleWeb.__new__(AppleWeb);a.closed=False;a.enabled=True;a.state={}
        a.startup_since=time.monotonic();a.startup_timer=7;a.poll=Mock();a.changed=Mock()
        a.bridge=Mock(connected=True);a.last_enable=True
        return a

    def test_connect_polls_immediately_and_disconnect_discards_stale_metadata(self):
        a=self.app();a._connection_changed();a.poll.assert_called_once();a.changed.assert_called_once()
        a.bridge.connected=False;a.state={'title':'Old fixture'};a._connection_changed()
        self.assertEqual(a.state,{});self.assertIsNone(a.last_enable)

    def test_quick_startup_poll_is_bounded_and_stops_when_ready(self):
        a=self.app();self.assertTrue(a._startup_poll());a.poll.assert_called_once()
        a.state={'ready':True};self.assertFalse(a._startup_poll());self.assertEqual(a.startup_timer,0)
        a.state={};a.startup_since=time.monotonic()-26
        self.assertFalse(a._startup_poll());self.assertEqual(a.poll.call_count,1)
        a.startup_since=time.monotonic();a.enabled=False;self.assertFalse(a._startup_poll())
