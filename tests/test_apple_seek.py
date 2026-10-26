import sys,time,unittest
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from apple_web import AppleWeb

class AppleSeekTests(unittest.TestCase):
    def app(self):
        a=AppleWeb.__new__(AppleWeb);a.closed=False;a.state={'id':'123','position':5};a.changed=Mock()
        a.seek_next=None;a.seek_timer=0;a.seek_intent=None;a.seek_inflight=False;a.error='';a.pool=Mock();a.poll=Mock()
        return a

    def test_drag_coalesces_and_serializes_latest_position_and_moves_ui_immediately(self):
        a=self.app();first=Future();last=Future();a.pool.submit.side_effect=[first,last]
        with patch('apple_web.GLib.timeout_add',return_value=7) as timer,patch('apple_web.GLib.idle_add',side_effect=lambda fn,*args:fn(*args)):
            for p in (10,20,30):a.action('seek',position=p)
            timer.assert_called_once();self.assertEqual(a.state['position'],30);a.pool.submit.assert_not_called()
            a._flush_seek();a.pool.submit.assert_called_once_with(a.request,'seek',position=30)
            a.action('seek',position=40);self.assertEqual(a.pool.submit.call_count,1)
            first.set_result({'ok':True});self.assertEqual(timer.call_count,2)
            a._flush_seek();self.assertEqual(a.pool.submit.call_args.kwargs,{'position':40})
            last.set_result({'ok':True});self.assertFalse(a.seek_inflight)

    def test_old_status_cannot_snap_progress_back_and_confirmation_releases_intent(self):
        a=self.app();a.seek_intent=(50,time.monotonic(),'123');a.seek_inflight=True
        old={'id':'123','position':5,'spatial':{'seeking':False}}
        self.assertEqual(a._seek_state(old)['position'],50)
        a.seek_inflight=False
        preparing={'id':'123','position':50,'spatial':{'seeking':True}}
        self.assertEqual(a._seek_state(preparing)['position'],50);self.assertIsNotNone(a.seek_intent)
        done={'id':'123','position':50.2,'spatial':{'seeking':False}}
        self.assertEqual(a._seek_state(done)['position'],50.2);self.assertIsNone(a.seek_intent)
        a.seek_intent=(50,time.monotonic(),'123')
        other={'id':'456','position':0}
        self.assertEqual(a._seek_state(other),other);self.assertIsNone(a.seek_intent)
        a.seek_intent=(50,time.monotonic()-13,'123')
        self.assertEqual(a._seek_state(old),old);self.assertIsNone(a.seek_intent)

if __name__=='__main__':unittest.main()
