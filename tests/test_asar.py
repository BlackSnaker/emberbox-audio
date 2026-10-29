"""Every local JS dependency must exist in the shipped backend archive."""
import json,re,struct,sys,tempfile,unittest
from pathlib import Path,PurePosixPath
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from asar_pack import pack


class AsarDependencies(unittest.TestCase):
    def test_all_local_requires_are_shipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'app.asar';pack(Path(__file__).resolve().parents[1]/'src/apple_web_host',target)
            data=target.read_bytes();header_size=struct.unpack_from('<I',data,12)[0]
            files=json.loads(data[16:16+header_size])['files'];start=8+struct.unpack_from('<I',data,4)[0]
            for name,entry in files.items():
                if not name.endswith(('.js','.cjs')):continue
                offset=start+int(entry['offset']);source=data[offset:offset+entry['size']].decode()
                for dependency in re.findall(r"require\(['\"](\./[^'\"]+)['\"]\)",source):
                    key=str(PurePosixPath(name).parent/dependency)
                    self.assertIn(key,files,f'{name} requires missing packaged module {key}')


if __name__=='__main__':unittest.main()
