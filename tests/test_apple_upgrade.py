"""An adapter update must not restore playback before account authorization."""
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from apple_web import AppleWeb

class AppleUpgrade(TestCase):
    def test_restore_waits_for_the_authorized_new_engine(self):
        app=AppleWeb.__new__(AppleWeb)
        app.closed=False;app.enabled=True;app._start_engine=Mock()
        states=[{'ready':True,'authorized':False,'integrationVersion':10},
                {'ready':True,'authorized':True,'integrationVersion':10}]
        observed=[]
        def request(method,**params):
            if method=='status':observed.append(states.pop(0));return observed[-1]
            if method=='play':
                self.assertEqual(len(observed),2)
                self.assertTrue(observed[-1]['authorized'])
            return {}
        app.bridge=Mock(connected=True);app.bridge.request.side_effect=request
        with patch('apple_web.subprocess.run'),patch('apple_web.time.sleep'):
            app._upgrade({'id':'123','authorized':True,'playing':False,'position':42})
        app.bridge.request.assert_any_call('play',kind='songs',id='123',position=42,paused=True)
        app._start_engine.assert_called_once()
