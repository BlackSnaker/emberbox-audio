import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import karaoke_model as model


class ModelTests(unittest.TestCase):
    def test_same_size_corrupt_weights_are_rejected_and_not_executed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);weight=root/'model.onnx';python=root/'python';stamp=root/'ready.json'
            valid=b'original model fixture';sha=hashlib.sha256(valid).hexdigest()
            weight.write_bytes(valid);python.touch();stamp.write_text(json.dumps({'version':1,'sha256':sha}))
            with patch.multiple(model,MODEL=weight,PYTHON=python,STAMP=stamp,MODEL_SIZE=len(valid),MODEL_SHA=sha):
                self.assertTrue(model.ready());self.assertEqual(model.verified_model(),weight)
                weight.write_bytes(b'x'*len(valid))
                with self.assertRaisesRegex(RuntimeError,'ai-model-invalid'):model.verified_model()
                python.unlink();self.assertFalse(model.ready())

    def test_cancelled_download_never_promotes_partial_model(self):
        import io,threading
        stop=threading.Event();stop.set()
        with tempfile.TemporaryDirectory() as folder:
            destination=Path(folder)/'model'
            with patch('karaoke_model.urllib.request.urlopen',return_value=io.BytesIO(b'partial')):
                with self.assertRaises(InterruptedError):model._download('https://example.test/model',destination,'invalid',100,lambda _:None,stop)
            self.assertFalse(destination.exists());self.assertFalse(destination.with_suffix('.part').exists())


if __name__=='__main__':unittest.main()
