from pathlib import Path
import json
import os
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import apple_setup


class AppleSetupTests(unittest.TestCase):
    def test_existing_connection_retains_profile_without_relogin_or_probe(self):
        value={'runtime':'fixture','cdm_module':'fixture','profile':'existing-owned-profile'}
        with patch('apple_setup.configured',return_value=value),patch('apple_setup.subprocess.run') as probe:
            self.assertEqual(apple_setup.prepare(),value)
            probe.assert_not_called()

    def test_failed_drm_check_does_not_save_configuration(self):
        with patch('apple_setup.configured',return_value=None),patch('apple_setup.valid',return_value=True), \
             patch('apple_setup.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='{"engine":"fixture","capabilities":{"aac":"probably","widevine":false}}')), \
             patch('apple_setup.save') as save:
            with self.assertRaisesRegex(apple_setup.SetupError,'INCOMPATIBLE_ENGINE'):
                apple_setup.prepare('/fixture/runtime','/fixture/module')
            save.assert_not_called()

    def test_successful_check_saves_private_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings/apple-engine.json'
            reply='{"engine":"fixture","capabilities":{"aac":"probably","widevine":true,"mediaKeysCreated":true}}'
            with patch('apple_setup.ENGINE_CONFIG',path),patch('apple_setup.configured',return_value=None), \
                 patch('apple_setup.valid',return_value=True),patch('apple_setup.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=reply)):
                result=apple_setup.prepare('/fixture/runtime','/fixture/module')
            self.assertEqual(json.loads(path.read_text()),result)
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
