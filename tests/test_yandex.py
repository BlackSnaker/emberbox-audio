from pathlib import Path
import json
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock
from concurrent.futures import Future
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import yandex_web
from stream_target import Target,matches


class YandexTests(unittest.TestCase):
    def test_existing_profile_reuses_updated_apple_engine(self):
        old={'runtime':'/old/engine','cdm_module':'/old/module','profile':'/owned/yandex-profile'}
        shared={'runtime':'/working/apple-engine','cdm_module':'/working/module','profile':'/private/apple-profile'}
        with patch('yandex_web.apple_setup.configured',side_effect=[old,shared]),patch('yandex_web.apple_setup.save') as save:
            result=yandex_web.prepare()
        self.assertEqual(result['runtime'],shared['runtime'])
        self.assertEqual(result['profile'],old['profile'])
        save.assert_called_once_with(result,yandex_web.ENGINE_CONFIG)

    def test_first_play_waits_for_source_enable_acknowledgement(self):
        app=yandex_web.YandexWeb.__new__(yandex_web.YandexWeb)
        app.enabled=True;app.closed=False;app.error='';app.ensure_started=lambda:None
        app.bridge=SimpleNamespace(connected=True,request=Mock(return_value={'ok':True}))
        app.request('wave')
        self.assertEqual(app.bridge.request.call_args_list[0].args,('enable',))
        self.assertEqual(app.bridge.request.call_args_list[1].args,('wave',))
        app.bridge.request.reset_mock();app.enabled=False
        self.assertEqual(app.request('wave'),{'skipped':True})
        app.bridge.request.assert_not_called()
        app.request('transport',action='pause')
        app.bridge.request.assert_called_once_with('transport',action='pause')

    def test_old_adapter_updates_once_and_polling_preserves_action_errors(self):
        app=yandex_web.YandexWeb.__new__(yandex_web.YandexWeb)
        app.closed=False;app.error='Useful playback error';app.upgrade_attempted=False
        app.pool=Mock();app.changed=Mock()
        future=Future();future.set_result({'integrationVersion':2,'authorized':False,'ready':False})
        app._status_done(future)
        self.assertEqual(app.error,'Useful playback error')
        self.assertTrue(app.upgrading)
        app.pool.submit.assert_called_once()
        app._status_done(future)
        app.pool.submit.assert_called_once()

    def test_runtime_reuse_keeps_account_profiles_separate(self):
        shared={'runtime':'/fixture/runtime','cdm_module':'/fixture/cdm','profile':'/private/apple-profile'}
        with tempfile.TemporaryDirectory() as folder:
            destination=Path(folder)/'yandex-engine.json'
            with patch('yandex_web.ENGINE_CONFIG',destination),patch('yandex_web.CONFIG_DIR',Path(folder)), \
                 patch('yandex_web.apple_setup.configured',side_effect=[None,shared]):
                config=yandex_web.prepare()
            self.assertEqual(config['runtime'],shared['runtime'])
            self.assertEqual(config['cdm_module'],shared['cdm_module'])
            self.assertNotEqual(config['profile'],shared['profile'])
            self.assertEqual(Path(config['profile']).name,'yandex-web-profile')
            self.assertEqual(json.loads(destination.read_text()),config)
            self.assertEqual(destination.stat().st_mode&0o777,0o600)
            self.assertEqual(shared['profile'],'/private/apple-profile')

    def test_existing_yandex_profile_is_retained(self):
        value={'runtime':'engine','cdm_module':'module','profile':'owned-yandex-profile'}
        with patch('yandex_web.apple_setup.configured',return_value=value),patch('yandex_web.apple_setup.prepare') as prepare:
            self.assertEqual(yandex_web.prepare(),value)
            prepare.assert_not_called()

    def test_launch_uses_independent_unit_profile_and_socket(self):
        config={'runtime':'/engine','cdm_module':'/cdm','profile':'/owned/yandex'}
        app=yandex_web.YandexWeb.__new__(yandex_web.YandexWeb)
        app.start_lock=threading.Lock();app.bridge=SimpleNamespace(path=Path('/private/yandex-player.sock'))
        with patch.object(Path,'read_text',return_value=json.dumps(config)), \
             patch('yandex_web.subprocess.run',side_effect=[SimpleNamespace(returncode=1),SimpleNamespace(returncode=0)]) as run:
            app._start_engine()
        command=run.call_args.args[0]
        self.assertIn('--unit='+yandex_web.APP_ID+'-yandex',command)
        self.assertEqual(command[command.index('--service')+1],'yandex')
        self.assertEqual(command[command.index('--profile')+1],'/owned/yandex')
        self.assertEqual(command[command.index('--socket')+1],'/private/yandex-player.sock')

    def test_yandex_spectrum_does_not_capture_other_apps(self):
        target=Target('yandex-music',12345,'','yandex-native')
        with patch('stream_target.descendant',side_effect=lambda pid,owner:pid==owner), \
             patch.object(Path,'resolve',return_value=Path('/engine/EmberboxYandex')):
            self.assertTrue(matches({'application.process.id':'12345'},target))
            self.assertFalse(matches({'application.process.id':'444','application.name':'Spotify'},target))
