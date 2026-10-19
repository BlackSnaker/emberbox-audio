import concurrent.futures
import io
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from apple_bridge import AppleBridge
from apple_native_host import read_message,write_message

ROOT=Path(__file__).resolve().parents[1]


class AppleBridgeTests(unittest.TestCase):
    def test_framing_rejects_large_and_short_messages(self):
        stream=io.BytesIO();write_message(stream,{'result':{'items':[]}});stream.seek(0)
        self.assertEqual(read_message(stream),{'result':{'items':[]}})
        for raw in (b'x',struct.pack('@I',3)+b'a',struct.pack('@I',3000000)):
            with self.assertRaises(ValueError):read_message(io.BytesIO(raw))

    def test_real_native_host_round_trip(self):
        with tempfile.TemporaryDirectory(prefix='emberbox-bridge-') as folder, patch.dict(os.environ,{'XDG_RUNTIME_DIR':folder}):
            bridge=AppleBridge()
            host=subprocess.Popen([sys.executable,str(ROOT/'src/apple_native_host.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+3
                while not bridge.connected and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue(bridge.connected)
                self.assertEqual(bridge.path.stat().st_mode & 0o777,0o600)
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future=pool.submit(bridge.request,'browse',category='albums',offset=0)
                    request=read_message(host.stdout)
                    self.assertEqual(request['method'],'browse')
                    self.assertEqual(request['params']['category'],'albums')
                    write_message(host.stdin,{'id':request['id'],'result':{'items':[{'title':'Fixture album'}]}})
                    self.assertEqual(future.result(timeout=3),{'items':[{'title':'Fixture album'}]})
                with self.assertRaises(ValueError):bridge.request('executeJavaScript',code='anything')
            finally:
                host.terminate();host.communicate(timeout=3);bridge.close()
