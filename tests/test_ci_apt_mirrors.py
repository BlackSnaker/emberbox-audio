"""Runner mirrors can be direct deb822 sources or file-backed mirror lists."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from ci_apt_mirrors import configure


class MirrorTests(unittest.TestCase):
    def test_direct_and_file_backed_mirrors_and_retry_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'sources.list.d').mkdir()
            files = {
                'sources.list.d/ubuntu.sources': 'URIs: http://us-east-2.ec2.archive.ubuntu.com/ubuntu/\nSuites: noble noble-updates\nSigned-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n',
                'apt-mirrors.txt': 'http://azure.archive.ubuntu.com/ubuntu\n',
                'sources.list': 'deb http://archive.ubuntu.com/ubuntu noble main\n',
                'sources.list.d/vendor.list': 'deb https://packages.example.org/ubuntu noble main\n',
                'sources.list.d/mirror.sources': 'URIs: mirror+file:/etc/apt/apt-mirrors.txt\n',
            }
            for name, value in files.items():
                (root/name).write_text(value)
            configure(root)
            direct = (root/'sources.list.d/ubuntu.sources').read_text()
            self.assertEqual(direct, files['sources.list.d/ubuntu.sources'].replace(
                'http://us-east-2.ec2.archive.ubuntu.com', 'https://archive.ubuntu.com'))
            self.assertEqual((root/'apt-mirrors.txt').read_text(), 'https://archive.ubuntu.com/ubuntu\n')
            self.assertIn('https://archive.ubuntu.com/ubuntu', (root/'sources.list').read_text())
            for name in ('sources.list.d/vendor.list', 'sources.list.d/mirror.sources'):
                self.assertEqual((root/name).read_text(), files[name])
            policy = (root/'apt.conf.d/80ember-ci-network').read_text()
            self.assertIn('Acquire::Retries "3";', policy)
            self.assertIn('Acquire::https::Timeout "30";', policy)
            configure(root)
            self.assertEqual((root/'sources.list.d/ubuntu.sources').read_text(), direct)
