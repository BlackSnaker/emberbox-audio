"""Public clip preparation is reusable, bounded and never publishes partials."""
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import motion_cache

URL='https://mvod.itunes.apple.com/fixture/loop.mp4'


class Process:
    def __init__(self,command,timeout=False):
        self.command=command;self.code=None;self.timeout=timeout
        Path(command[-1]).write_bytes(b'original fixture payload')
    def poll(self):return self.code
    def wait(self,timeout=None):
        if self.timeout and self.code is None:raise subprocess.TimeoutExpired(self.command,timeout)
        self.code=0 if self.code is None else self.code;return self.code
    def terminate(self):self.code=-15
    def kill(self):self.code=-9


class MotionCache(unittest.TestCase):
    def test_remux_is_silent_atomic_and_reused_on_next_loop_or_resize(self):
        with tempfile.TemporaryDirectory() as folder:
            commands=[];handles=[]
            def launch(command,**_options):commands.append(command);return Process(command)
            with patch.object(motion_cache.subprocess,'Popen',side_effect=launch):
                first=motion_cache.cached_clip('ffmpeg',URL,threading.Event(),handles.append,folder)
                second=motion_cache.cached_clip('ffmpeg',URL,threading.Event(),handles.append,folder)
            self.assertEqual(first,second);self.assertTrue(first.startswith('file:'))
            self.assertEqual(len(commands),1)
            self.assertIn('-an',commands[0]);self.assertIn('copy',commands[0])
            self.assertEqual(commands[0].count('-map'),1)
            self.assertEqual(len(list(Path(folder).glob('*.mp4'))),1)
            self.assertFalse(list(Path(folder).glob('*.part')))
            self.assertIsNone(handles[-1])

    def test_timeout_and_cancellation_leave_no_incomplete_clip(self):
        with tempfile.TemporaryDirectory() as folder:
            handles=[]
            with patch.object(motion_cache.subprocess,'Popen',side_effect=lambda command,**_:Process(command,True)):
                with self.assertRaises(subprocess.TimeoutExpired):
                    motion_cache.cached_clip('ffmpeg',URL,threading.Event(),handles.append,folder)
            self.assertIsNotNone(handles[0].poll())
            self.assertFalse(list(Path(folder).iterdir()))
            stop=threading.Event();stop.set()
            with patch.object(motion_cache.subprocess,'Popen') as launch:
                self.assertEqual(motion_cache.cached_clip('ffmpeg',URL,stop,handles.append,folder),'')
                launch.assert_not_called()

    def test_size_limit_discards_truncated_payload(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(motion_cache,'CLIP_LIMIT',8):
            with patch.object(motion_cache.subprocess,'Popen',side_effect=lambda command,**_:Process(command)):
                self.assertEqual(motion_cache.cached_clip('ffmpeg',URL,threading.Event(),lambda _:None,folder),'')
            self.assertFalse(list(Path(folder).iterdir()))


if __name__=='__main__':unittest.main()
